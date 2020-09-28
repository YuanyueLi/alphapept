# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06_score.ipynb (unless otherwise specified).

__all__ = ['filter_score', 'filter_precursor', 'get_q_values', 'cut_fdr', 'cut_global_fdr', 'get_x_tandem_score',
           'score_x_tandem', 'filter_with_x_tandem', 'score_psms', 'get_ML_features', 'train_RF', 'score_ML',
           'filter_with_ML', 'get_protein_groups', 'perform_protein_grouping', 'score_hdf', 'score_hdf_parallel',
           'protein_groups_hdf', 'protein_groups_hdf_parallel', 'save_report_as_npz']

# Cell
import numpy as np
import pandas as pd
import logging
import alphapept.io

def filter_score(df, mode='multiple'):
    """
    Filter df by score
    TODO: PSMS could still have the same socre when having modifications at multiple positions that are not distinguishable.
    Only keep one.

    """
    df["rank"] = df.groupby("query_idx")["score"].rank("dense", ascending=False).astype("int")
    df = df[df["rank"] == 1]

    # in case two hits have the same score and therfore rank only accept the first one
    df = df.drop_duplicates("query_idx")

    if 'dist' in df.columns:
        df["feature_rank"] = df.groupby("feature_idx")["dist"].rank("dense", ascending=True).astype("int")
        df["raw_rank"] = df.groupby("raw_idx")["score"].rank("dense", ascending=False).astype("int")

        if mode == 'single':
            df_filtered = df[(df["feature_rank"] == 1) & (df["raw_rank"] == 1) ]
            df_filtered = df_filtered.drop_duplicates("raw_idx")

        elif mode == 'multiple':
            df_filtered = df[(df["feature_rank"] == 1)]

        else:
            raise NotImplementedError('Mode {} not implemented yet'.format(mode))

    else:
        df_filtered = df

    # TOD: this needs to be sorted out, for modifications -> What if we have MoxM -> oxMM, this will screw up with the filter sequence part
    return df_filtered

def filter_precursor(df):
    """
    Filter df by precursor
    Allow each precursor only once.

    """
    df["rank_precursor"] = (
        df.groupby("precursor")["score"].rank("dense", ascending=False).astype("int")
    )
    df_filtered = df[df["rank_precursor"] == 1]

    return df_filtered

# Cell
from numba import njit
@njit
def get_q_values(fdr_values):
    """
    Calculate q values from fdr_values
    """
    q_values = np.zeros_like(fdr_values)
    min_q_value = np.max(fdr_values)
    for i in range(len(fdr_values) - 1, -1, -1):
        fdr = fdr_values[i]
        if fdr < min_q_value:
            min_q_value = fdr
        q_values[i] = min_q_value

    return q_values

# Cell
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def cut_fdr(df, fdr_level=0.01, plot=True):
    """
    Cuts a dataframe with a given fdr level

    Args:
        fdr_level: fdr level that should be used
        plot: flag to enable plot

    Returns:
        cutoff: df with psms within fdr
        cutoff_value: numerical value of score cutoff

    Raises:

    """

    df["target"] = ~df["decoy"]

    df = df.sort_values(by=["score","decoy"], ascending=False)
    df = df.reset_index()

    df["target_cum"] = np.cumsum(df["target"])
    df["decoys_cum"] = np.cumsum(df["decoy"])

    df["fdr"] = df["decoys_cum"] / df["target_cum"]
    df["q_value"] = get_q_values(df["fdr"].values)

    last_q_value = df["q_value"].iloc[-1]
    first_q_value = df["q_value"].iloc[0]

    if last_q_value <= fdr_level:
        logging.info('Last q_value {:.3f} of dataset is smaller than fdr_level {:.3f}'.format(last_q_value, fdr_level))
        cutoff_index = len(df)-1

    elif first_q_value >= fdr_level:
        logging.info('First q_value {:.3f} of dataset is larger than fdr_level {:.3f}'.format(last_q_value, fdr_level))
        cutoff_index = 0

    else:
        cutoff_index = df[df["q_value"].gt(fdr_level)].index[0] - 1

    cutoff_value = df.loc[cutoff_index]["score"]
    cutoff = df[df["score"] >= cutoff_value]

    targets = df.loc[cutoff_index, "target_cum"]
    decoy = df.loc[cutoff_index, "decoys_cum"]

    fdr = df.loc[cutoff_index, "fdr"]


    logging.info(
        "{:,} target ({:,} decoy) of {} PSM. fdr {:.6f} for a cutoff of {:.2f} ".format(
            targets, decoy, len(df), fdr, cutoff_value
        )
    )

    if plot:
        import matplotlib.pyplot as plt
        import seaborn as sns
        plt.figure(figsize=(10, 5))
        plt.plot(df["score"], df["fdr"])
        plt.axhline(0.01, color="k", linestyle="--")

        plt.axvline(cutoff_value, color="r", linestyle="--")
        plt.title("fdr vs Cutoff value")
        plt.xlabel("Score")
        plt.ylabel("fdr")
        # plt.savefig('fdr.png')
        plt.show()

        bins = np.linspace(np.min(df["score"]), np.max(df["score"]), 100)
        plt.figure(figsize=(10, 5))
        sns.distplot(df[df["decoy"]]["score"].values, label="decoy", bins=bins)
        sns.distplot(df[~df["decoy"]]["score"].values, label="target", bins=bins)
        plt.xlabel("Score")
        plt.ylabel("Frequency")
        plt.title("Score vs Class")
        plt.legend()
        plt.show()

    cutoff = cutoff.reset_index(drop=True)
    return cutoff_value, cutoff

# Cell

def cut_global_fdr(data, analyte_level='sequence', fdr_level=0.01, plot=True, **kwargs):
    """
    Function to estimate and filter by global peptide or protein fdr

    """
    logging.info('Global FDR on {}'.format(analyte_level))
    data_sub = data[[analyte_level,'score','decoy']]
    data_sub_unique = data_sub.groupby([analyte_level,'decoy'], as_index=False).agg({"score": "max"})

    analyte_levels = ['precursor', 'sequence', 'protein']

    if analyte_level in analyte_levels:
        agg_score = data_sub_unique.groupby([analyte_level,'decoy'])['score'].max().reset_index()
    else:
        raise Exception('analyte_level should be either sequence or protein. The selected analyte_level was: {}'.format(analyte_level))

    agg_cval, agg_cutoff = cut_fdr(agg_score, fdr_level=fdr_level, plot=plot)

    agg_report = pd.merge(data,
                          agg_cutoff,
                          how = 'inner',
                          on = [analyte_level,'decoy'],
                          suffixes=('', '_'+analyte_level),
                          validate="many_to_one")
    return agg_report

# Cell

import networkx as nx

def get_x_tandem_score(df):

    b = df['b_hits'].astype('int').apply(lambda x: np.math.factorial(x)).values
    y = df['y_hits'].astype('int').apply(lambda x: np.math.factorial(x)).values
    x_tandem = np.log(b.astype('float')*y.astype('float')*df['matched_int'].values)

    x_tandem[x_tandem==-np.inf] = 0

    return x_tandem

def score_x_tandem(df, fdr_level = 0.01, plot = True, **kwargs):
    logging.info('Scoring using X-Tandem')
    df['score'] = get_x_tandem_score(df)
    df['decoy'] = df['sequence'].str[-1].str.islower()

    df = filter_score(df)
    df = filter_precursor(df)
    cval, cutoff = cut_fdr(df, fdr_level, plot)

    return cutoff

def filter_with_x_tandem(df, fdr_level = 0.01):
    """
    Filters a dataframe using an x_tandem score
    """
    logging.info('Filter df with x_tandem score')

    df['score'] = get_x_tandem_score(df)
    df['decoy'] = df['sequence'].str[-1].str.islower()

    df = filter_score(df)
    df = filter_precursor(df)

    return df

# Cell

def score_psms(df, score = 'y_hits', fdr_level = 0.01, plot = True, **kwargs):
    if score in df.columns:
        df['score'] = df[score]
    else:
        raise ValueError("The specified 'score' {} is not available in 'df'.".format(score))
    df['decoy'] = df['sequence'].str[-1].str.islower()

    df = filter_score(df)
    df = filter_precursor(df)
    cval, cutoff = cut_fdr(df, fdr_level, plot)

    return cutoff

# Cell

import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV

import matplotlib.pyplot as plt
import seaborn as sns

from .fasta import count_missed_cleavages, count_internal_cleavages


def get_ML_features(df, protease='trypsin', **kwargs):
    df['decoy'] = df['sequence'].str[-1].str.islower()

    df['abs_delta_m_ppm'] = np.abs(df['delta_m_ppm'])
    df['naked_sequence'] = df['sequence'].str.replace('[a-z]|_', '')
    df['n_AA']= df['naked_sequence'].str.len()
    df['matched_ion_fraction'] = df['hits']/(2*df['n_AA'])

    #df['decoy_reversed_seq'] = df['naked_sequence']
    #df.loc[df['decoy'] == True, 'decoy_reversed_seq'] = df['decoy_reversed_seq'].apply(lambda x: x[::-1])
    df['n_missed'] = df['naked_sequence'].apply(lambda x: count_missed_cleavages(x, protease))
    df['n_internal'] = df['naked_sequence'].apply(lambda x: count_internal_cleavages(x, protease))
    #df = df.drop(columns=['decoy_reversed_seq'])

    mz_bin, mz_count = np.unique(np.floor(df.mz/100), return_counts=True)
    mz_count = np.log(mz_count)
    df['ln_mz_range'] = df['mz'].apply(lambda x: mz_count[mz_bin == np.floor(x/100)])
    df = df.astype({"ln_mz_range": float})

    df['charge_'] = df['charge']
    df = pd.get_dummies(df, columns=['charge'])
    df = df.rename(columns={'charge_': 'charge'})

    count_seq = df.groupby('naked_sequence')['naked_sequence'].count()
    df['ln_sequence'] = np.log(count_seq[df['naked_sequence']].values)
    df['x_tandem'] = get_x_tandem_score(df)

    return df

def train_RF(df,
             features = ['y_hits','b_hits','matched_int',
                         'delta_m_ppm','abs_delta_m_ppm',
                        'charge_2.0','charge_3.0','charge_4.0','charge_5.0',
                        'n_AA','n_missed','n_internal','ln_sequence','x_tandem',
                        'db_mass_density','db_weighted_mass_density',
                        'db_mass_density_digit','db_weighted_mass_density_digit',
                        'hits','matched_ion_fraction','ln_mz_range'],
             train_fdr_level = 0.1,
             ini_score = 'y_hits',
             min_train = 5000,
             test_size = 0.8,
             max_depth = [5,25,50],
             max_leaf_nodes = [150,200,250],
             n_jobs=3,
             scoring='accuracy',
             plot = True,
             random_state = 42,
             **kwargs):

    # Setup ML pipeline
    scaler = StandardScaler()
    rfc = RandomForestClassifier(random_state=random_state) # class_weight={False:1,True:5},
    ## Initiate scaling + classification pipeline
    pipeline = Pipeline([('scaler', scaler), ('clf', rfc)])
    parameters = {'clf__max_depth':(max_depth), 'clf__max_leaf_nodes': (max_leaf_nodes)}
    ## Setup grid search framework for parameter selection and internal cross validation
    cv = GridSearchCV(pipeline, param_grid=parameters, cv=5, scoring=scoring,
                     verbose=0,return_train_score=True,n_jobs=n_jobs)

    # Prepare target and decoy df
    df['decoy'] = df['sequence'].str[-1].str.islower()
    df['target'] = ~df['decoy']
    df['score'] = df[ini_score]
    dfT = df[~df.decoy]
    dfD = df[df.decoy]

    # Select high scoring targets (<= train_fdr_level)
    df_prescore = filter_score(df)
    df_prescore = filter_precursor(df_prescore)
    scored = cut_fdr(df_prescore, fdr_level = train_fdr_level, plot=False)[1]
    highT = scored[scored.decoy==False]
    dfT_high = dfT[dfT['query_idx'].isin(highT.query_idx)]
    dfT_high = dfT_high[dfT_high['db_idx'].isin(highT.db_idx)]

    # Determine the number of psms for semi-supervised learning
    n_train = int(dfT_high.shape[0])
    if dfD.shape[0] < n_train:
        n_train = int(dfD.shape[0])
        logging.info("The total number of available decoys is lower than the initial set of high scoring targets.")
    if n_train < min_train:
        raise ValueError("There are fewer high scoring targets or decoys than required by 'min_train'.")

    # Subset the targets and decoys datasets to result in a balanced dataset
    df_training = dfT_high.sample(n=n_train, random_state=random_state).append(dfD.sample(n=n_train, random_state=random_state))

    # Select training and test sets
    X = df_training[features]
    y = df_training['target'].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(X.values, y.values, test_size=test_size, random_state=random_state, stratify=y.values)

    # Train the classifier on the training set via 5-fold cross-validation and subsequently test on the test set
    logging.info('Training & cross-validation on {} targets and {} decoys'.format(np.sum(y_train),X_train.shape[0]-np.sum(y_train)))
    cv.fit(X_train,y_train)

    logging.info('The best parameters selected by 5-fold cross-validation were {}'.format(cv.best_params_))
    logging.info('The train {} was {}'.format(scoring, cv.score(X_train, y_train)))
    logging.info('Testing on {} targets and {} decoys'.format(np.sum(y_test),X_test.shape[0]-np.sum(y_test)))
    logging.info('The test {} was {}'.format(scoring, cv.score(X_test, y_test)))

    # Inspect feature importances
    if plot:
        feature_importances=cv.best_estimator_.named_steps['clf'].feature_importances_
        indices = np.argsort(feature_importances)[::-1][:40]
        g = sns.barplot(y=X.columns[indices][:40],
                        x = feature_importances[indices][:40],
                        orient='h', palette='RdBu')
        g.set_xlabel("Relative importance",fontsize=12)
        g.set_ylabel("Features",fontsize=12)
        g.tick_params(labelsize=9)
        g.set_title("Feature importance")
        plt.show()

    return cv

def score_ML(df,
             trained_classifier,
             features = ['y_hits','b_hits','matched_int',
                         'delta_m_ppm','abs_delta_m_ppm',
                        'charge_2.0','charge_3.0','charge_4.0','charge_5.0',
                        'n_AA','n_missed','n_internal','ln_sequence','x_tandem',
                        'db_mass_density','db_weighted_mass_density',
                        'db_mass_density_digit','db_weighted_mass_density_digit',
                        'hits','matched_ion_fraction','ln_mz_range'],
            fdr_level = 0.01,
            plot=True,
             **kwargs):
    logging.info('Scoring using Machine Learning')
    # Apply the classifier to the entire dataset
    df_new = df.copy()
    df_new['score'] = trained_classifier.predict_proba(df_new[features])[:,1]
    df_new = filter_score(df_new)
    df_new = filter_precursor(df_new)
    cval, cutoff = cut_fdr(df_new, fdr_level, plot)

    return cutoff


def filter_with_ML(df,
             trained_classifier,
             features = ['y_hits','b_hits','matched_int',
                         'delta_m_ppm','abs_delta_m_ppm',
                        'charge_2.0','charge_3.0','charge_4.0','charge_5.0',
                        'n_AA','n_missed','n_internal','ln_sequence','x_tandem',
                        'db_mass_density','db_weighted_mass_density',
                        'db_mass_density_digit','db_weighted_mass_density_digit',
                        'hits','matched_ion_fraction','ln_mz_range'],
            fdr_level = 0.01,
            plot=True,
             **kwargs):

    """
    Filters a dataframe using ML
    """
    logging.info('Filter df with x_tandem score')
    # Apply the classifier to the entire dataset
    df_new = df.copy()
    df_new['score'] = trained_classifier.predict_proba(df_new[features])[:,1]
    df_new = filter_score(df_new)
    df_new = filter_precursor(df_new)

    return df_new

# Cell
import networkx as nx
def get_protein_groups(data, pept_dict, fasta_dict, callback = None, **kwargs):
    """
    Function to perform protein grouping by razor approach
    ToDo: implement callback for solving
    Each protein is indicated with a p -> protein index
    """
    G=nx.Graph()

    found_proteins = {}

    for i in range(len(data)):
        line = data.iloc[i]
        seq = line['sequence']
        score = line['score']
        if seq in pept_dict:
            proteins = pept_dict[seq]
            if len(proteins) > 1:
                for protein in proteins:
                    G.add_edge(str(i), 'p'+str(protein), score=score)
            else: #if there is only one PSM just add to this protein
                if 'p'+str(proteins[0]) in found_proteins.keys():
                    found_proteins['p'+str(proteins[0])] = found_proteins['p'+str(proteins[0])] + [str(i)]
                else:
                    found_proteins['p'+str(proteins[0])] = [str(i)]

        if callback:
            callback((i+1)/len(data))

    logging.info('A total of {:,} proteins with unique PSMs found'.format(len(found_proteins)))

    connected_groups = np.array([list(c) for c in sorted(nx.connected_components(G), key=len, reverse=True)])
    n_groups = len(connected_groups)


    logging.info('A total of {} ambigious proteins'.format(len(connected_groups)))

    #Solving with razor:
    found_proteins_razor = {}
    for a in connected_groups:
        H = G.subgraph(a)

        shared_proteins = list(np.array(a)[np.array(list(i[0] == 'p' for i in a))])

        removed = []

        while len(shared_proteins) > 0:

            neighbors_list = []

            for node in shared_proteins:
                neighbors = list(H.neighbors(node))
                n_neigbhors = len(neighbors)

                if node in G:
                    if node in found_proteins.keys():
                        n_neigbhors+= len(found_proteins[node])

                neighbors_list.append((n_neigbhors, node, neighbors))

            neighbors_list.sort()

            #Remove the last entry:

            count, node, psms = neighbors_list[-1]

            shared_proteins.remove(node)

            psms = [_ for _ in psms if _ not in removed]

            removed += psms

            found_proteins_razor[node] = psms

    #Put back in Df
    report = data.copy()
    report['protein'] = ''
    report['protein_group'] = ''

    for protein_str in found_proteins.keys():
        protein = int(protein_str[1:])
        indexes = [int(_) for _ in found_proteins[protein_str]]
        report.loc[indexes, 'protein'] = fasta_dict[protein]['name']
        report.loc[indexes, 'protein_group'] = fasta_dict[protein]['name']

    report['razor'] = False
    for protein_str in found_proteins_razor.keys():
        protein = int(protein_str[1:])
        indexes = [int(_) for _ in found_proteins_razor[protein_str]]

        report.loc[indexes, 'protein'] = fasta_dict[protein]['name']
        report.loc[indexes, 'razor'] = True

    for a in connected_groups:
        protein_group = list(np.array(a)[np.array(list(i[0] == 'p' for i in a))])
        psms = [int(i) for i in a if i not in protein_group]
        report.loc[psms, 'protein_group'] = ','.join([fasta_dict[int(_[1:])]['name'] for _ in protein_group])

    return report

def perform_protein_grouping(data, pept_dict, fasta_dict, **kwargs):
    """
    Wrapper function to perform protein grouping by razor approach

    """
    data_sub = data[['sequence','score','decoy']]
    data_sub_unique = data_sub.groupby(['sequence','decoy'], as_index=False).agg({"score": "max"})

    targets = data_sub_unique[data_sub_unique.decoy == False]
    targets = targets.reset_index(drop=True)
    protein_targets = get_protein_groups(targets, pept_dict, fasta_dict, **kwargs)

    decoys = data_sub_unique[data_sub_unique.decoy == True]
    decoys = decoys.reset_index(drop=True)
    protein_decoys = get_protein_groups(decoys, pept_dict, fasta_dict, **kwargs)

    protein_groups = protein_targets.append(protein_decoys)
    protein_groups_app = protein_groups[['sequence','decoy','protein','razor']]
    protein_report = pd.merge(data,
                                protein_groups_app,
                                how = 'inner',
                                on = ['sequence','decoy'],
                                validate="many_to_one")
    return protein_report

# Cell
import os
from multiprocessing import Pool


def score_hdf(to_process):

    path, settings = to_process

    skip = False

    ms_file = alphapept.io.MS_Data_File(path, is_overwritable=True)

    try:
        df = ms_file.read(dataset_name='second_search')

        logging.info('Found second search psms for scoring.')
    except KeyError:
        df = ms_file.read(dataset_name='first_search')
        logging.info('No second search psms for scoring found. Using first search.')

    if len(df) == 0:
        skip = True
        logging.info('Dataframe does not contain data. Skipping scoring step.')

    if not skip:
        df = get_ML_features(df, **settings['fasta'])

        if settings["general"]["score"] == 'random_forest':
            cv = train_RF(df)
            df = filter_with_ML(df, cv)
        elif settings["general"]["score"] == 'x_tandem':
            df = filter_with_x_tandem(df)
        else:
            raise NotImplementedError('Scoring method {} not implemented.'.format(settings["general"]["score"]))

        df = cut_global_fdr(df, analyte_level='precursor',  plot=False, **settings['search'])

        ms_file.write(df, dataset_name="peptide_fdr")

        logging.info('FDR on peptides complete. For {} FDR found {:,} targets and {:,} decoys.'.format(settings["search"]["peptide_fdr"], df['target'].sum(), df['decoy'].sum()) )


def score_hdf_parallel(settings, callback=None):

    paths = []

    for _ in settings['experiment']['file_paths']:
        base, ext = os.path.splitext(_)
        hdf_path = base+'.ms_data.hdf'
        paths.append(hdf_path)

    to_process = [(path, settings) for path in paths]

    n_processes = settings['general']['n_processes']

    if len(to_process) == 1:
        score_hdf(to_process[0])
    else:

        with Pool(n_processes) as p:
            max_ = len(to_process)
            for i, _ in enumerate(p.imap_unordered(score_hdf, to_process)):
                if callback:
                    callback((i+1)/max_)

# Cell
def protein_groups_hdf(to_process):

    skip = False
    path, pept_dict, fasta_dict, settings = to_process
    ms_file = alphapept.io.MS_Data_File(path, is_overwritable=True)
    try:
        df = ms_file.read(dataset_name='peptide_fdr')
    except KeyError:
        skip = True

    if not skip:
        df_pg = perform_protein_grouping(df, pept_dict, fasta_dict, callback = None)

        df_pg = cut_global_fdr(df_pg, analyte_level='protein',  plot=False, **settings['search'])

        ms_file.write(df_pg, dataset_name="protein_fdr")

        logging.info('FDR on proteins complete. For {} FDR found {:,} targets and {:,} decoys. A total of {:,} proteins found.'.format(settings["search"]["protein_fdr"], df_pg['target'].sum(), df_pg['decoy'].sum(), len(set(df_pg['protein']))))


def protein_groups_hdf_parallel(settings, pept_dict, fasta_dict, callback=None):

    paths = []

    for _ in settings['experiment']['file_paths']:
        base, ext = os.path.splitext(_)
        hdf_path = base+'.ms_data.hdf'
        paths.append(hdf_path)

    to_process = [(path, pept_dict.copy(), fasta_dict.copy(), settings) for path in paths]

    n_processes = settings['general']['n_processes']

    if len(to_process) == 1:
        protein_groups_hdf(to_process[0])
    else:

        with Pool(n_processes) as p:
            max_ = len(to_process)
            for i, _ in enumerate(p.imap_unordered(protein_groups_hdf, to_process)):
                if callback:
                    callback((i+1)/max_)

# Cell
def save_report_as_npz(
    df,
    fasta_dict,
    pept_dict,
    report_path_npz
):

    to_save = {}
    to_save["df"] = df
    to_save["fasta_dict"] = fasta_dict
    to_save["pept_dict"] = np.array(pept_dict)

    np.savez(report_path_npz, **to_save)

    logging.info("Raw File saved to {}".format(report_path_npz))
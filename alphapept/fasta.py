# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_fasta.ipynb (unless otherwise specified).

__all__ = ['get_missed_cleavages', 'cleave_sequence', 'count_missed_cleavages', 'count_internal_cleavages', 'parse',
           'list_to_numba', 'get_decoy_sequence', 'swap_KR', 'swap_AL', 'get_decoys', 'add_decoy_tag', 'add_fixed_mods',
           'get_mod_pos', 'get_isoforms', 'add_variable_mods', 'add_fixed_mod_terminal', 'add_fixed_mods_terminal',
           'add_variable_mods_terminal', 'get_unique_peptides', 'generate_peptides', 'get_precmass', 'get_fragmass',
           'get_frag_dict', 'get_spectrum', 'get_spectra', 'read_fasta_file', 'read_fasta_file_entries', 'read_fasta',
           'check_sequence', 'add_to_pept_dict', 'generate_library', 'generate_spectra', 'save_library']

# Cell
from alphapept import constants
import re

def get_missed_cleavages(sequences, n_missed_cleavages):
    """
    Combine cleaved sequences to get sequences with missed cleavages
    """
    missed = []
    for k in range(len(sequences)-n_missed_cleavages):
        missed.append(''.join(sequences[k-1:k+n_missed_cleavages]))

    return missed


def cleave_sequence(
    sequence="",
    num_missed_cleavages=0,
    protease="trypsin",
    min_length=6,
    max_length=65,
    **kwargs
):

    proteases = constants.protease_dict
    pattern = proteases[protease]

    p = re.compile(pattern)

    cutpos = [m.start()+1 for m in p.finditer(sequence)]
    cutpos.insert(0,0)
    cutpos.append(len(sequence))

    base_sequences = [sequence[cutpos[i]:cutpos[i+1]] for i in range(len(cutpos)-1)]

    sequences = base_sequences.copy()

    for i in range(1, num_missed_cleavages+1):
        sequences.extend(get_missed_cleavages(base_sequences, i))

    sequences = [_ for _ in sequences if len(_)>=min_length and len(_)<=max_length]

    return sequences

# Cell
import re
from alphapept import constants

def count_missed_cleavages(sequence="", protease="trypsin",**kwargs):
    """
    Counts the number of missed cleavages for a given sequence and protease
    """
    proteases = constants.protease_dict
    protease = proteases[protease]
    p = re.compile(protease)
    n_missed = len(p.findall(sequence))
    return n_missed

def count_internal_cleavages(sequence="", protease="trypsin",**kwargs):
    """
    Counts the number of internal cleavage sites for a given sequence and protease
    """
    proteases = constants.protease_dict
    protease = proteases[protease]
    match = re.search(protease,sequence[-1]+'_')
    if match:
        n_internal = 0
    else:
        n_internal = 1
    return n_internal

# Cell
from numba import njit
from numba.typed import List

@njit
def parse(peptide):
    """
    Parser to parse peptide strings
    """
    if "_" in peptide:
        peptide = peptide.split("_")[0]
    parsed = List()
    string = ""

    for i in peptide:
        string += i
        if i.isupper():
            parsed.append(string)
            string = ""

    return parsed

def list_to_numba(a_list):
    numba_list = List()

    for element in a_list:
        numba_list.append(element)

    return numba_list

# Cell
@njit
def get_decoy_sequence(peptide, AL_swap=True, KR_swap = True):
    """
    Reverses a sequence and adds the '_decoy' tag.

    """
    pep = parse(peptide)
    rev_pep = pep[::-1]

    if AL_swap:
        rev_pep = swap_AL(rev_pep)

    if KR_swap:
        rev_pep = swap_KR(rev_pep)

    rev_pep = "".join(rev_pep)

    return rev_pep


@njit
def swap_KR(peptide):
    """
    Swaps a terminal K or R. Note: Only if AA is not modified.
    """
    if peptide[-1] == 'K':
        peptide[-1] = 'R'
    elif peptide[-1] == 'R':
        peptide[-1] = 'K'

    return peptide


@njit
def swap_AL(peptide):
    """
    Swaps a A with L. Note: Only if AA is not modified.
    """
    i = 0
    while i < len(range(len(peptide) - 1)):
        if peptide[i] == "A":
            peptide[i] = peptide[i + 1]
            peptide[i + 1] = "A"
            i += 1
        elif peptide[i] == "L":
            peptide[i] = peptide[i + 1]
            peptide[i + 1] = "L"
            i += 1
        i += 1

    return peptide

def get_decoys(peptide_list):
    """
    Wrapper to get decoys for lists of peptides
    """
    decoys = []
    decoys.extend([get_decoy_sequence(peptide) for peptide in peptide_list])
    return decoys

def add_decoy_tag(peptides):
    """
    Adds a _decoy tag to a list of peptides
    """
    return [peptide + "_decoy" for peptide in peptides]

# Cell
def add_fixed_mods(seqs, mods_fixed, **kwargs):
    """
    Adds fixed modifications to sequences.
    """
    if not mods_fixed:
        return seqs
    else:
        for mod_aa in mods_fixed:
            seqs = [seq.replace(mod_aa[-1], mod_aa) for seq in seqs]
        return seqs

# Cell
def get_mod_pos(variable_mods_r, sequence):
    """
    Returns a list with of tuples with all possibilities for modified an unmodified AAs.
    """
    modvar = []
    for c in sequence:
        if c in variable_mods_r.keys():
            modvar.append((c, variable_mods_r[c]))
        else:
            modvar.append((c,))

    return modvar

# Cell

from itertools import product
def get_isoforms(variable_mods_r, sequence, max_isoforms):
    """
    Function to generate isoforms for a given peptide - returns a list of isoforms.
    The original sequence is included in the list
    """
    modvar = get_mod_pos(variable_mods_r, sequence)
    isoforms = []
    i = 0
    for o in product(*modvar):
        if i < max_isoforms:
            i += 1
            isoforms.append("".join(o))

        else:
            break

    return isoforms

# Cell
from itertools import chain

def add_variable_mods(peptide_list, mods_variable, max_isoforms, **kwargs):
    if not mods_variable:
        return peptide_list
    else:
        mods_variable_r = {}
        for _ in mods_variable:
            mods_variable_r[_[-1]] = _

        peptide_list = [get_isoforms(mods_variable_r, peptide, max_isoforms) for peptide in peptide_list]
        return list(chain.from_iterable(peptide_list))

# Cell
def add_fixed_mod_terminal(peptides, mod):
    """
    Adds fixed terminal modifications
    """
    # < for left side (N-Term), > for right side (C-Term)
    if "<^" in mod: #Any n-term, e.g. a<^
        peptides = [mod[:-2] + peptide for peptide in peptides]
    elif ">^" in mod: #Any c-term, e.g. a>^
        peptides = [peptide[:-1] + mod[:-2] + peptide[-1] for peptide in peptides]
    elif "<" in mod: #only if specific AA, e.g. ox<C
        peptides = [peptide[0].replace(mod[-1], mod[:-2]+mod[-1]) + peptide[1:] for peptide in peptides]
    elif ">" in mod:
        peptides = [peptide[:-1] + peptide[-1].replace(mod[-1], mod[:-2]+mod[-1]) for peptide in peptides]
    else:
        # This should not happen
        raise ("Invalid fixed terminal modification {}.".format(key))
    return peptides

def add_fixed_mods_terminal(peptides, mods_fixed_terminal, **kwargs):
    """
    Wrapper to add fixed mods on sequences and lists of mods
    """
    if mods_fixed_terminal == []:
        return peptides
    else:
        # < for left side (N-Term), > for right side (C-Term)
        for key in mods_fixed_terminal:
            peptides = add_fixed_mod_terminal(peptides, key)
        return peptides

# Cell
def add_variable_mods_terminal(peptides, mods_variable_terminal, **kwargs):
    "Function to add variable terminal modifications"
    if not mods_variable_terminal:
        return peptides
    else:
        new_peptides_n = peptides.copy()

        for key in mods_variable_terminal:
            if "<" in key:
                # Only allow one variable mod on one end
                new_peptides_n.extend(
                    add_fixed_mod_terminal(peptides, key)
                )
        new_peptides_n = get_unique_peptides(new_peptides_n)
        # N complete, let's go for c-terminal
        new_peptides_c = new_peptides_n
        for key in mods_variable_terminal:
            if ">" in key:
                # Only allow one variable mod on one end
                new_peptides_c.extend(
                    add_fixed_mod_terminal(new_peptides_n, key)
                )

        return get_unique_peptides(new_peptides_c)

def get_unique_peptides(peptides):
    return list(set(peptides))

# Cell
def generate_peptides(peptide, **kwargs):
    """
    Wrapper to get modified peptides from a peptide
    """
    mod_peptide = add_fixed_mods_terminal([peptide], kwargs['mods_fixed_terminal_prot'])

    mod_peptide = add_variable_mods_terminal(mod_peptide, kwargs['mods_variable_terminal_prot'])

    peptides = []
    [peptides.extend(cleave_sequence(_, **kwargs)) for _ in mod_peptide]

    #Regular peptides
    mod_peptides = add_fixed_mods(peptides, **kwargs)
    mod_peptides = add_fixed_mods_terminal(mod_peptides, **kwargs)
    mod_peptides = add_variable_mods_terminal(mod_peptides, **kwargs)
    mod_peptides = add_variable_mods(mod_peptides, **kwargs)

    #Decoys:
    decoy_peptides = get_decoys(peptides)

    mod_peptides_decoy = add_fixed_mods(decoy_peptides, **kwargs)
    mod_peptides_decoy = add_fixed_mods_terminal(mod_peptides_decoy, **kwargs)
    mod_peptides_decoy = add_variable_mods_terminal(mod_peptides_decoy, **kwargs)
    mod_peptides_decoy = add_variable_mods(mod_peptides_decoy, **kwargs)

    mod_peptides_decoy = add_decoy_tag(mod_peptides_decoy)

    mod_peptides.extend(mod_peptides_decoy)

    return mod_peptides

# Cell
from numba import njit
import numpy as np

@njit
def get_precmass(parsed_pep, mass_dict):
    """
    Calculate the mass of the neutral precursor
    """
    tmass = mass_dict["H2O"]
    for _ in parsed_pep:
        tmass += mass_dict[_]

    return tmass

# Cell

@njit
def get_fragmass(parsed_pep, mass_dict):
    """
    Calculate the masses of the fragment ions
    """
    n_frags = (len(parsed_pep) - 1) * 2

    frag_masses = np.zeros(n_frags, dtype=np.float64)
    frag_type = np.zeros(n_frags, dtype=np.int8)

    # b-ions -> 0
    n_frag = 0
    frag_m = mass_dict["Proton"]
    for _ in parsed_pep[:-1]:
        frag_m += mass_dict[_]
        frag_masses[n_frag] = frag_m
        frag_type[n_frag] = 0
        n_frag += 1

    # y-ions -> 1
    frag_m = mass_dict["Proton"] + mass_dict["H2O"]
    for _ in parsed_pep[::-1][:-1]:
        frag_m += mass_dict[_]
        frag_masses[n_frag] = frag_m
        frag_type[n_frag] = 1
        n_frag += 1

    return frag_masses, frag_type

# Cell
def get_frag_dict(parsed_pep, mass_dict):
    """
    Calculate the masses of the fragment ions
    """
    n_frags = (len(parsed_pep) - 1) * 2

    frag_dict = {}

    # b-ions -> 0
    n_frag = 0
    frag_m = mass_dict["Proton"]

    for _ in parsed_pep[:-1]:
        frag_m += mass_dict[_]
        n_frag += 1

        frag_dict['b' + str(n_frag)] = frag_m

    # y-ions -> 1
    n_frag = 0
    frag_m = mass_dict["Proton"] + mass_dict["H2O"]
    for _ in parsed_pep[::-1][:-1]:
        frag_m += mass_dict[_]
        n_frag += 1
        frag_dict['y' + str(n_frag)] = frag_m

    return frag_dict

# Cell
@njit
def get_spectrum(peptide, mass_dict):
    parsed_peptide = parse(peptide)

    fragmasses, fragtypes = get_fragmass(parsed_peptide, mass_dict)
    sortindex = np.argsort(fragmasses)
    fragmasses = fragmasses[sortindex]
    fragtypes = fragtypes[sortindex]

    precmass = get_precmass(parsed_peptide, mass_dict)

    return (precmass, peptide, fragmasses, fragtypes)

@njit
def get_spectra(peptides, mass_dict):
    spectra = []

    for i in range(len(peptides)):
        spectra.append(get_spectrum(peptides[i], mass_dict))

    return spectra

# Cell
from Bio import SeqIO
import os
from glob import glob

def read_fasta_file(fasta_filename=""):
    """
    given a fasta_file read fasta file line by line, return progress
    """
    with open(fasta_filename, "rt") as handle:
        iterator = SeqIO.parse(handle, "fasta")
        while iterator:
            try:
                record = next(iterator)
                parts = record.id.split("|")  # pipe char
                if len(parts) > 1:
                    id = parts[1]
                else:
                    id = record.name
                sequence = str(record.seq)
                entry = {
                    "id": id,
                    "name": record.name,
                    "description": record.description,
                    "sequence": sequence,
                }

                yield entry
            except StopIteration:
                break


def read_fasta_file_entries(fasta_filename=""):
    """
    Function to count entries in fasta file
    """
    with open(fasta_filename, "rt") as handle:
        iterator = SeqIO.parse(handle, "fasta")
        count = 0
        while iterator:
            try:
                record = next(iterator)
                count+=1
            except StopIteration:
                break

        return count



def read_fasta(path):
    """
    Wrapper to read multiple files.
    """
    if os.path.isdir(path):
        paths = glob(path + "/*.fasta")
    else:
        paths = glob(path)

    if len(paths) == 0:
        raise KeyError("Not a valid Fasta Path: {}.".format(path))

    for fasta_file in paths:
        for entry in read_fasta_file(fasta_file):
            yield entry

def check_sequence(element, AAs):
    """
    Checks wheter a sequence from a FASTA entry contains valid AAs
    """
    if not set(element['sequence']).issubset(AAs):
        print('Error. This FASTA Entry contains unknown AAs and will be skipped: \n {}\n'.format(element))
        return False
    else:
        return True

# Cell
def add_to_pept_dict(pept_dict, new_peptides, i):
    """
    Add peptides to the peptide dictionary
    """
    added_peptides = List()
    for peptide in new_peptides:
        if peptide in pept_dict:
            pept_dict[peptide].append(i)
        else:
            pept_dict[peptide] = [i]
            added_peptides.append(peptide)

    return pept_dict, added_peptides

# Cell
from collections import OrderedDict

def generate_library(mass_dict, fasta_path, callback = None, contaminants_path = None, **kwargs):
    """
    Function to generate a library from a fasta file
    """
    to_add = List()
    fasta_dict = OrderedDict()
    fasta_index = 0

    pept_dict = {}

    if type(fasta_path) is str:
        fasta_path = [fasta_path]
        n_fastas = 1

    elif type(fasta_path) is list:
        n_fastas = len(fasta_path)

    for f_id, fasta_file in enumerate(fasta_path):
        n_entries = read_fasta_file_entries(fasta_file)

        fasta_generator = read_fasta(fasta_file)

        for element in fasta_generator:
            if check_sequence(element, constants.AAs):
                fasta_dict[fasta_index] = element
                mod_peptides = generate_peptides(element["sequence"], **kwargs)
                pept_dict, added_seqs = add_to_pept_dict(pept_dict, mod_peptides, fasta_index)
                if len(added_seqs) > 0:
                    to_add.extend(added_seqs)

            fasta_index += 1

            if callback:
                callback(fasta_index/n_entries/n_fastas+f_id)

    if contaminants_path:
        fasta_generator = read_fasta(contaminants_path)

        for element in fasta_generator:
            if check_sequence(element, constants.AAs):
                fasta_dict[fasta_index] = element
                mod_peptides = generate_peptides(element["sequence"], **kwargs)
                pept_dict, added_seqs = add_to_pept_dict(pept_dict, mod_peptides, fasta_index)
                if len(added_seqs) > 0:
                    to_add.extend(added_seqs)

            fasta_index += 1

    return to_add, pept_dict, fasta_dict


def generate_spectra(to_add, mass_dict, callback = None):
    """
    Function to generate a library from a fasta file
    """

    if len(to_add) > 0:

        if callback: #Chunk the spectra to get a progress_bar
            spectra = []

            stepsize = int(np.ceil(len(to_add)/1000))

            for i in range(0, len(to_add), stepsize):
                sub = to_add[i:i + stepsize]
                spectra.extend(get_spectra(sub, mass_dict))
                callback((i+1)/len(to_add))

        else:
            spectra = get_spectra(to_add, mass_dict)
    else:
        raise ValueError("No spectra to generate.")

    return spectra

# Cell
from .io import list_to_numpy_f32


def save_library(spectra, pept_dict, fasta_dict, library_path, **kwargs):
    """
    Function to save a library to the *.npz format.
    """

    precmasses, seqs, fragmasses, fragtypes = zip(*spectra)
    sortindex = np.argsort(precmasses)

    to_save = {}

    to_save["precursors"] = np.array(precmasses)[sortindex]
    to_save["seqs"] = np.array(seqs)[sortindex]
    to_save["pept_dict"] = pept_dict
    to_save["fasta_dict"] = fasta_dict
    to_save["fragmasses"] = list_to_numpy_f32(np.array(fragmasses)[sortindex])
    to_save["fragtypes"] = list_to_numpy_f32(np.array(fragtypes)[sortindex])

    to_save["bounds"] = np.sum(to_save['fragmasses']>=0,axis=0).astype(np.int64)

    np.savez(library_path, **to_save)

    return library_path
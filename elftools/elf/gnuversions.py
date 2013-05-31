#------------------------------------------------------------------------------
# elftools: elf/gnuversions.py
#
# ELF sections
#
# Yann Rouillard (yann@pleiades.fr.eu.org)
# This code is in the public domain
#------------------------------------------------------------------------------
from ..construct import CString
from ..common.utils import struct_parse, elf_assert
from .sections import Section, Symbol


class Version(object):
    """ Version object - representing a version definition or dependency
        entry from a "Version Needed" or a "Version Dependency" table section.

        This kind of entry contains a pointer to an array of auxiliary entries
        that store the information about version names or dependencies.
        These entries are not stored in this object and should be accessed
        through the appropriate method of a section object which will return
        an iterator of VersionAuxiliary objects.

        Similarly to Section objects, allows dictionary-like access to
        verdef/verneed entry
    """
    def __init__(self, entry, name=None):
        self.entry = entry
        self.name = name

    def __getitem__(self, name):
        """ Implement dict-like access to entry
        """
        return self.entry[name]


class VersionAuxiliary(object):
    """ Version Auxiliary object - representing an auxiliary entry of a version
        definition or dependency entry

        Similarly to Section objects, allows dictionary-like access to the
        verdaux/vernaux entry
    """
    def __init__(self, entry, name):
        self.entry = entry
        self.name = name

    def __getitem__(self, name):
        """ Implement dict-like access to entries
        """
        return self.entry[name]


class GNUVerNeedSection(Section):
    """ ELF SUNW or GNU Version Needed table section.
        Has an associated StringTableSection that's passed in the constructor.
    """
    def __init__(self, header, name, stream, elffile, stringtable):
        super(GNUVerNeedSection, self).__init__(header, name, stream)
        self.elffile = elffile
        self.elfstructs = self.elffile.structs
        self.stringtable = stringtable
        self._has_indexes = None

    def num_versions(self):
        """ Number of version dependency in the table
        """
        return self['sh_info']

    def has_indexes(self):
        """ Return True if at least one version definition entry has an index
            that is stored in the vna_other field.
            This information is used for symbol versioning
        """
        if self._has_indexes is None:
            self._has_indexes = False
            for _, vernaux_iter in self.iter_versions():
                for vernaux in vernaux_iter:
                    if vernaux['vna_other']:
                        self._has_indexes = True
                        break

        return self._has_indexes

    def get_version(self, index):
        """ Get the version information located at index #n in the table
            Return boths the verneed structure and the vernaux structure
            that contains the name of the version
        """
        for verneed, vernaux_iter in self.iter_versions():
            for vernaux in vernaux_iter:
                if vernaux['vna_other'] == index:
                    return verneed, vernaux

        return None

    def _iter_version_auxiliaries(self, entry_offset, count):
        """ Yield all auxiliary entries of a version dependency
        """
        for _ in range(count):
            entry = struct_parse(
                        self.elfstructs.Elf_Vernaux,
                        self.stream,
                        stream_pos=entry_offset)

            name = self.stringtable.get_string(entry['vna_name'])
            version_aux = VersionAuxiliary(entry, name)
            yield version_aux

            if not entry['vna_next']:
                break

            entry_offset += entry['vna_next']

    def iter_versions(self):
        """ Yield all the version dependencies entries in the table
            Each time it returns the main version dependency structure
            and an iterator to walk through its auxiliaries entries
        """
        entry_offset = self['sh_offset']
        for _ in range(self.num_versions()):
            entry = struct_parse(
                self.elfstructs.Elf_Verneed,
                self.stream,
                stream_pos=entry_offset)

            name = self.stringtable.get_string(entry['vn_file'])
            elf_assert(entry['vn_cnt'] > 0,
                'Expected number of version names to be > 0 for'
                'version definition %s' % name)

            verneed = Version(entry, name)
            aux_entries_offset = entry_offset + entry['vn_aux']
            vernaux_iter = self._iter_version_auxiliaries(aux_entries_offset,
                                                          entry['vn_cnt'])
            yield verneed, vernaux_iter

            if not entry['vn_next']:
                break

            entry_offset += entry['vn_next']


class GNUVerDefSection(Section):
    """ ELF SUNW or GNU Version Definition table section.
        Has an associated StringTableSection that's passed in the constructor.
    """
    def __init__(self, header, name, stream, elffile, stringtable):
        super(GNUVerDefSection, self).__init__(header, name, stream)
        self.elffile = elffile
        self.elfstructs = self.elffile.structs
        self.stringtable = stringtable

    def num_versions(self):
        """ Number of version definitions in the table
        """
        return self['sh_info']

    def get_version(self, index):
        """ Get the version information located at index #n in the table
            Return boths the verdef structure and an iterator to retrieve
            both the version names and dependencies in the form of
            verdaux entries
        """
        for verdef, verdaux_iter in self.iter_versions():
            if verdef['vd_ndx'] == index:
                return verdef, verdaux_iter

        return None

    def _iter_version_auxiliaries(self, entry_offset, count):
        """ Yield all auxiliary entries of a version definition
        """
        for _ in range(count):
            entry = struct_parse(
                        self.elfstructs.Elf_Verdaux,
                        self.stream,
                        stream_pos=entry_offset)

            name = self.stringtable.get_string(entry['vda_name'])
            vernaux = VersionAuxiliary(entry, name)
            yield vernaux

            if not entry['vda_next']:
                break

            entry_offset += entry['vda_next']

    def iter_versions(self):
        """ Yield all the version definition entries in the table
            Each time it returns the main version definition structure
            and an iterator to walk through its auxiliaries entries
        """
        entry_offset = self['sh_offset']
        for _ in range(self.num_versions()):
            entry = struct_parse(
                self.elfstructs.Elf_Verdef,
                self.stream,
                stream_pos=entry_offset)

            elf_assert(entry['vd_cnt'] > 0,
                'Expected number of version names to be > 0'
                'for version definition at index %i' % entry['vd_ndx'])

            verdef = Version(entry)
            aux_entries_offset = entry_offset + entry['vd_aux']
            verdaux_iter = self._iter_version_auxiliaries(aux_entries_offset,
                                                          entry['vd_cnt'])
            yield verdef, verdaux_iter

            if not entry['vd_next']:
                break

            entry_offset += entry['vd_next']


class GNUVerSymSection(Section):
    """ ELF SUNW or GNU Versym table section.
        Has an associated SymbolTableSection that's passed in the constructor.
    """
    def __init__(self, header, name, stream, elffile, symboltable):
        super(GNUVerSymSection, self).__init__(header, name, stream)
        self.elffile = elffile
        self.elfstructs = self.elffile.structs
        self.symboltable = symboltable

    def num_symbols(self):
        """ Number of symbols in the table
        """
        return self['sh_size'] // self['sh_entsize']

    def get_symbol(self, n):
        """ Get the symbol at index #n from the table (Symbol object)
            It begins at 1 and not 0 since the first entry is used to
            store the current version of the syminfo table
        """
        # Grab the symbol's entry from the stream
        entry_offset = self['sh_offset'] + n * self['sh_entsize']
        entry = struct_parse(
            self.elfstructs.Elf_Versym,
            self.stream,
            stream_pos=entry_offset)
        # Find the symbol name in the associated symbol table
        name = self.symboltable.get_symbol(n).name
        return Symbol(entry, name)

    def iter_symbols(self):
        """ Yield all the symbols in the table
        """
        for i in range(self.num_symbols()):
            yield self.get_symbol(i)
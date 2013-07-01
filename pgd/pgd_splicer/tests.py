from django.core import management
from django.test import TestCase
from pgd_splicer.models import ftp_update_settings
import os
import datetime
import ftplib
import urllib
import shutil

# JMT: Due to a quirk with InnoDB and MySQL, an error may be generated
# when the fixtures are loaded.  The error will be something like this:

# IntegrityError: (1452, 'Cannot add or update a child row: a foreign
# key constraint fails (`test_pgd_dev`.`pgd_core_sidechain_arg`,
# CONSTRAINT `residue_id_refs_id_ab080b67` FOREIGN KEY (`residue_id`)
# REFERENCES `pgd_core_residue` (`id`))')

# If this occurs, modify the settings.py to disable foreign key
# checks during tests.  Place the following line after DATABASE_PORT:

# if 'test' in sys.argv:
#     DATABASE_OPTIONS = {'init_command': 'SET foreign_key_checks=0'}


class MonkeyPatch:

    # This class monkeypatches the network modules to provide a controlled environment for testing.

    # The cullpdb files contain references to:
    #  - 1TWF
    #  - 3CGZ
    #  - 3CGX
    #  - 3CGM
    #  - 1MWW

    # For comparison, the database fixture contains:
    #  - 1TWF
    #  - 3CGZ
    #  - 1MWQ
    #  - 3CGM
    #  - 1MWW

    # Files for all six proteins are available as well.

    @staticmethod
    def sitefile(filename):
        # All test files are stored in the same place.
        return os.path.join('pgd_splicer/testfiles', filename)

    @staticmethod
    def localfile(filename):
        # All local files are stored in the localdir.
        return os.path.join(ftp_update_settings.PDB_LOCAL_DIR, filename)

    class FTP:
        def __init__(self, host):
            self.host = host

        def login(self):
            pass

        def cwd(self, remotedir):
            pass

        def sendcmd(self, command):
            cmdlist = command.split(' ')
            if cmdlist[0] == 'MDTM':
                filename = cmdlist[1]
                try:
                    rawmtime = os.path.getmtime(MonkeyPatch.sitefile(filename))
                    # return 20090301142529 for '03/01/2009 14:25:29 GMT'
                    return "213 %s" % datetime.datetime.fromtimestamp(rawmtime).strftime('%Y%m%d%H%M%S')
                except OSError:
                    # If file does not exist, the FTP server will return a permanent error.
                    # NB: should be error_perm but we will use False
                    return False
            else:
                # NB: Raise exception if unsupported command is used.
                return False

        def size(self, filename):
            # If the file exists, return its size.  If it doesn't, return None.
            try:
                return os.path.getsize(MonkeyPatch.sitefile(filename))
            except OSError:
                return None

        def retrbinary(self, command, callback, blocksize=8192, rest='REST'):
            # If the file exists, 'download' it.  If it doesn't, return False.
            cmdlist = command.split(' ')
            if cmdlist[0] == 'RETR':
                filename = cmdlist[1]
                try:
                    with open(MonkeyPatch.sitefile(filename)) as f:
                        while 1:
                            data = f.read(blocksize)
                            if not data:
                                break
                            callback(data)
                except OSError:
                    return False
            else:
                # NB: Raise exception if unsupported command is used.
                return False

    class urlopen:
        def __init__(self, url, data=None, proxies=None):
            # List of known URLs and their corresponding files.
            knownurls = {'http://dunbrack.fccc.edu/Guoli/culledpdb/': 'selection_page.txt',
                         'http://dunbrack.fccc.edu/Guoli/culledpdb//cullpdb_pc25_res3.0_R1.0_d130614_chains8184.gz': 'cullpdb_pc25.gz',
                         'http://dunbrack.fccc.edu/Guoli/culledpdb//cullpdb_pc90_res3.0_R1.0_d130614_chains24769.gz': 'cullpdb_pc90.gz'}

            self.url = url
            if self.url in knownurls:
                self.fileobj = open(MonkeyPatch.sitefile(knownurls[self.url]))
            else:
                self.fileobj = None

        def read(self):
            if self.fileobj is None:
                return None
            else:
                return self.fileobj.read()

        def readline(self):
            if self.fileobj is None:
                return None
            else:
                return self.fileobj.readline()

        def readlines(self):
            if self.fileobj is None:
                return None
            else:
                return self.fileobj.readlines()

        def fileno(self):
            if self.fileobj is None:
                return None
            else:
                return self.fileobj.fileno()

        def close(self):
            if self.fileobj is None:
                return None
            else:
                return self.fileobj.close()

        def info(self):
            if self.fileobj is None:
                return None
            else:
                return self.fileobj.info()

        def getcode(self):
            if self.fileobj is None:
                return 404
            else:
                return 200

        def geturl(self):
            return url

    def __enter__(self):
        # Override existing FTP and urlopen with our versions.
        self.old_FTP = ftplib.FTP
        ftplib.FTP = MonkeyPatch.FTP
        self.old_urlopen = urllib.urlopen
        urllib.urlopen = MonkeyPatch.urlopen

        # Remove all PDB entries and add ours from test files.
        codes = ['1mwq', '1mww', '1twf', '3cgm', '3cgx', '3cgz']
        for code in codes:
            pdbfile = 'pdb%s.ent.gz' % code
            shutil.copyfile(MonkeyPatch.sitefile(pdbfile), MonkeyPatch.localfile(pdbfile))

    def __exit__(self, type, value, traceback):
        # Clean up overrides
        ftplib.FTP = self.old_FTP
        urllib.urlopen = self.old_urlopen


class ManagementCommands(TestCase):

    fixtures = ['pgd_core']

    def test_fetch_old(self):

        with MonkeyPatch():
            # The management command should remove 1MWQ and add 3CGX.

            # This requires the 3CGX protein file but does not require the 1MWQ protein file.
            proteins = {'3cgx': 'pdb/pdb3cgx.ent.gz',
                        '1mwq': 'pdb/pdb1mwq.ent.gz'}

            # If the files exist, save the file dates, and set the clock back a day.
            olddates = {}

            # Set the file dates back one year if they exist.
            for key in proteins:
                olddates[key] = int(os.path.getmtime(proteins[key]))
                os.utime(proteins[key], (-1, olddates[key] - 86400))

            # Run the management command.
            management.call_command('fetch')

            # Only the 3CGX file should have been updated.
            self.assertEqual(int(os.path.getmtime(proteins['3cgx'])), olddates['3cgx'])
            self.assertEqual(int(os.path.getmtime(proteins['1mwq'])), olddates['1mwq'] - 86400)

            # The 3CGX file should be larger than 8192 bytes.
            self.assertGreater(os.path.getsize(proteins['3cgx']), 8192)

    def test_fetch_missing(self):

        with MonkeyPatch():
            # The management command should remove 1MWQ and add 3CGX.

            # This requires the 3CGX protein file but does not require the 1MWQ protein file.
            proteins = {'3cgx': 'pdb/pdb3cgx.ent.gz',
                        '1mwq': 'pdb/pdb1mwq.ent.gz'}

            # Remove the files if they exists.
            for key in proteins:
                if os.path.exists(proteins[key]):
                    os.remove(proteins[key])

            # Run the management command.
            management.call_command('fetch')

            # Only the 3CGX file should now exist.
            self.assertTrue(os.path.exists(proteins['3cgx']))
            self.assertFalse(os.path.exists(proteins['1mwq']))

            # The 3CGX file should be larger than 8192 bytes.
            self.assertGreater(os.path.getsize(proteins['3cgx']), 8192)

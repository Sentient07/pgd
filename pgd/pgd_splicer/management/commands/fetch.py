from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from pgd_core.models import Protein
from pgd_splicer.models import pdb_select_settings, ftp_update_settings
import urllib
import re
import gzip
from cStringIO import StringIO
import sys
import os
import time
from ftplib import FTP, error_perm
from datetime import datetime


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--url',
                    type='string',
                    default='http://dunbrack.fccc.edu/Guoli/culledpdb/',
                    help='URL for Dunbrack website'),
        make_option('--thresholds',
                    type='string',
                    default='25,90'),
        make_option('--resolution',
                    type='float',
                    dest='max_resolution',
                    default=3.0),
        make_option('--r_factor',
                    type='float',
                    dest='r_factor',
                    default=1.0),
        make_option('--report',
                    default=False,
                    help='write report to FILE'),
        make_option('--selection',
                    default=False,
                    help='write selections to FILE'),
        make_option('--verbose',
                    action='store_true',
                    default=False,
                    help='display verbose output'),
    )
    help = 'Retrieves missing proteins from the website.'

    tmpdir = pdb_select_settings.PDB_TMP_DIR
    pdbdir = pdb_select_settings.pdb_dir

    localdir = ftp_update_settings.PDB_LOCAL_DIR
    remotedir = ftp_update_settings.PDB_REMOTE_DIR
    ftphost = ftp_update_settings.PDB_FTP_HOST

    def filename(self, code):
        return 'pdb%s.ent.gz' % code[:4].lower()

    def make_prefix(self, started, outof, sofar):
        now = datetime.now()
        elapsed = now - started
        percent = 100.0 * sofar / outof
        remaining = str(elapsed * (outof - sofar) / sofar).split('.')[0]
        return "  [%d/%d %.1f%%, %s remaining]" % (sofar, outof, percent, remaining)

    def process_chunk(self, data):
        """ Callback for FTP download progress bar. """
        sys.stdout.write('.')
        sys.stdout.flush()
        self.infile.write(data)

    def fetch_pdb(self, ftp, code):
        filename = self.filename(code)
        localfile = os.path.join(self.localdir, filename)
        if os.path.exists(localfile):
            date = time.gmtime(os.path.getmtime(localfile))
        else:
            date = None

        try:
            resp = ftp.sendcmd('MDTM %s' % filename)
        except error_perm:
            # file not found on the website
            return 'notonsite'

        remote_date = time.strptime(resp[4:], '%Y%m%d%H%M%S')

        filechanged = False
        if date and time.mktime(remote_date) <= time.mktime(date):
            # file has not changed
            return 'unchanged'
        else:
            # file has changed
            filechanged = True

        # download the file
        size = ftp.size(filename)

        # remove existing file
        if os.path.exists(localfile):
            os.remove(localfile)

        self.infile = open(localfile, 'w')
        ftp.retrbinary('RETR %s' % filename, self.process_chunk)
        self.infile.close()
        sys.stdout.write('\n')
        if filechanged:
            return 'changed'
        else:
            return 'new'

    def handle(self, *args, **options):
        self.dunbrack_url = options['url']
        self.threshold = '|'.join([str(int(s)) for s in options['thresholds'].split(',')])
        self.max_resolution = options['max_resolution']
        self.r_factor = options['r_factor']
        self.verbose = options['verbose']

        print 'Reading selection page from website...'
        selection_page = urllib.urlopen(self.dunbrack_url).read()
        # FIXME: Grab the links based on the filenames!
        # <A href="link"> filename </A><br>
        pattern = '\s(cullpdb_pc(%s)_res%s_R%s_.*\d\.gz)' % (self.threshold, self.max_resolution, self.r_factor)

        files = re.findall(pattern, selection_page)

        self.proteins = {}
        regex_str = '(\w{4})(\w)\s+(\d+)\s+(\w+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)'
        regex_pattern = re.compile(regex_str)

        print 'Retrieving cull files...'
        for filename, threshold in files:
            # get file
            webfile = urllib.urlopen('/'.join([self.dunbrack_url, filename]))
            webfile_f = StringIO(webfile.read())

            # proteins = self.parse_file(path, resolution, threshold, proteins)
            _file = gzip.GzipFile(fileobj=webfile_f)
            # Discard first line (labels).
            _file.readline()

            for line in _file:
                match = regex_pattern.match(line)
                if match:
                    groups = match.groups()

                    if groups[0] in self.proteins:
                        # if protein already exists just update the additional
                        # chain information.  The properties should not change
                        # between records in the selection file.
                        protein = self.proteins[groups[0]]
                        if not groups[1] in protein['chains']:
                            protein['chains'].append(groups[1])
                    else:
                        # protein is not in proteins dict yet create initial
                        # structure from parsed properties.
                        resolution = float(groups[4])
                        if resolution > 0 and resolution <= self.max_resolution:
                            self.proteins[groups[0]] = {
                                'code': groups[0],
                                'chains': [groups[1]],
                                'resolution': groups[4],
                                'rfactor': groups[5],
                                'rfree': groups[6],
                                'threshold': threshold
                            }

        # store the date from the first file to use as the version.  The version will be
        # updated now even though the import has just begun.  Its marked to indicate that
        # it is still in progress
        date = files[0][0][26:32]
        version = '20%s-%s-%s' % (date[:2], date[2:4], date[4:])

        # compress chains
        for k, v in self.proteins.items():
            v['selchains'] = ''.join(v['chains'])

        # output selections
        if options['selection']:
            print 'Writing selections to %s...' % options['selection']
            with open(options['selection'], 'w') as out:
                out.write('VERSION: %s\n' % version)
                for k, v in self.proteins.items():
                    out.write('%(code)s %(selchains)s %(threshold)s %(resolution)s %(rfactor)s %(rfree)s\n' % v)

        self.indexed = set(Protein.objects.all().values_list('code', flat=True))
        self.desired = set(v['code'] for k, v in self.proteins.items())

        self.extras = self.indexed - self.desired
        self.missing = self.desired - self.indexed

        # 'unchanged': file is same local and remote
        # 'notonsite': file does not exist on remote
        # 'new': file was downloaded but did not exist on local
        # 'changed': file was downloaded but already existed on local
        self.files = {'unchanged': [],
                      'notonsite': [],
                      'new': [],
                      'changed': []}

        # fetch missing protein models
        if not os.path.exists(self.localdir):
            os.mkdir(self.localdir)

        # make FTP connection
        print 'Connecting via FTP to %s...' % self.ftphost
        ftp = FTP(self.ftphost)
        ftp.login()
        ftp.cwd(self.remotedir)

        # 'desired': to check all proteins for updates
        # 'missing': only download proteins that are not already here
        sofar = 0
        outof = len(self.desired)
        printper = int(outof / 1000) if outof > 1000 else 1
        started = datetime.now()
        for code in self.desired:
            # return code should indicate files type
            result = self.fetch_pdb(ftp, code)
            self.files[result].append(code)

        # output report
        if options['report']:
            print 'Writing report to %s...' % options['report']
            with open(options['report'], 'w') as out:
                if self.extras is []:
                    out.write('No extraneous proteins were found.\n')
                else:
                    out.write('Extraneous proteins: %d\n' % len(self.extras))
                    out.write(', '.join(sorted(self.extras)))
                    out.write('\n')
                if self.missing is []:
                    out.write('No proteins were missing.\n')
                else:
                    out.write('Missing proteins: %d\n' % len(self.missing))
                    out.write(', '.join(sorted(self.missing)))
                    out.write('\n')
                # fetch values default to []
                if self.files['changed'] is not []:
                    out.write('Proteins with newer versions on site: %d\n' % len(self.files['changed']))
                    out.write(', '.join(sorted(self.files['changed'])))
                    out.write('\n')
                if self.files['notonsite'] is not []:
                    out.write('Proteins not found on site: %d\n' % len(self.files['notonsite']))
                    out.write(', '.join(sorted(self.files['notonsite'])))
                    out.write('\n')
                if self.files['new'] is not []:
                    out.write('New proteins downloaded: %d\n' % len(self.files['new']))
                    out.write(', '.join(sorted(self.files['new'])))
                    out.write('\n')
                if self.files['changed'] is not []:
                    out.write('Changed proteins downloaded: %d\n' % len(self.files['changed']))
                    out.write(', '.join(sorted(self.files['changed'])))
                    out.write('\n')

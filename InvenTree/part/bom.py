"""
Functionality for Bill of Material (BOM) management.
Primarily BOM upload tools.
"""

from fuzzywuzzy import fuzz
import tablib
import os

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import Part, BomItem

from InvenTree.helpers import DownloadFile


def IsValidBOMFormat(fmt):
    """ Test if a file format specifier is in the valid list of BOM file formats """

    return fmt.strip().lower() in ['csv', 'xls', 'xlsx', 'tsv']


def MakeBomTemplate(fmt):
    """ Generate a Bill of Materials upload template file (for user download) """

    fmt = fmt.strip().lower()

    if not IsValidBOMFormat(fmt):
        fmt = 'csv'

    fields = [
        'Part',
        'Quantity',
        'Overage',
        'Reference',
        'Notes'
    ]

    data = tablib.Dataset(headers=fields).export(fmt)

    filename = 'InvenTree_BOM_Template.' + fmt

    return DownloadFile(data, filename)


class BomUploadManager:
    """ Class for managing an uploaded BOM file """

    # Fields which are absolutely necessary for valid upload
    REQUIRED_HEADERS = [
        'Part',
        'Quantity',
    ]

    # Fields which are not necessary but can be populated
    USEFUL_HEADERS = [
        'Reference',
        'Overage',
        'Notes'
    ]

    def __init__(self, bom_file, starting_row=2):
        """ Initialize the BomUpload class with a user-uploaded file object """
        self.starting_row = starting_row
        print("Starting on row", starting_row)
        self.process(bom_file)

    def process(self, bom_file):
        """ Process a BOM file """

        ext = os.path.splitext(bom_file.name)[-1].lower()

        if ext in ['.csv', '.tsv', ]:
            # These file formats need string decoding
            raw_data = bom_file.read().decode('utf-8')
        elif ext in ['.xls', '.xlsx']:
            raw_data = bom_file.read()
        else:
            raise ValidationError({'bom_file': _('Unsupported file format: {f}'.format(f=ext))})

        try:
            self.data = tablib.Dataset().load(raw_data)
        except tablib.UnsupportedFormat:
            raise ValidationError({'bom_file': _('Error reading BOM file (invalid data)')})

        # Now we have BOM data in memory!

        self.header_map = {}

        for header in self.REQUIRED_HEADERS:
            match = self.get_header(header)
            if match is None:
                raise ValidationError({'bom_file': _("Missing required field '{f}'".format(f=header))})
            else:
                self.header_map[header] = match

        for header in self.USEFUL_HEADERS:
            match = self.get_header(header)

            self.header_map[header] = match

        for k,v in self.header_map.items():
            print(k, '->', v)

    def get_header(self, header_name, threshold=80):
        """ Retrieve a matching column header from the uploaded file.
        If there is not an exact match, try to match one that is close.
        """

        headers = self.data.headers

        # First, try for an exact match
        for header in headers:
            if header == header_name:
                return header

        # Next, try for a case-insensitive match
        for header in headers:
            if header.lower() == header_name.lower():
                return header

        # Finally, look for a close match using fuzzy matching

        matches = []

        for header in headers:

            ratio = fuzz.partial_ratio(header, header_name)
            if ratio > threshold:
                matches.append({'header': header, 'match': ratio})

        if len(matches) > 0:
            matches = sorted(matches, key=lambda item: item['match'], reverse=True)

            # Return the field with the best match
            return matches[0]['header']

        return None

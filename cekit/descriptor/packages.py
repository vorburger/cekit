import os
import logging
import yaml

from cekit.config import Config
from cekit.errors import CekitError
from cekit.descriptor import Descriptor, Resource

logger = logging.getLogger('cekit')
config = Config()

packages_schema = [yaml.safe_load("""
map:
  content_sets: {type: any}
  content_sets_file: {type: str}
  repositories:
    seq:
      - {type: any}
  install:
    seq:
      - {type: any}""")]


repository_schema = yaml.safe_load("""
map:
  name: {type: str, required: True}
  id: {type: str}
  present: {type: bool}
  url:
    map:
      repository: {type: str}
      gpg: {type: str}
  rpm: {type: str}
  description: {type: str}
  odcs:
    map:
     pulp: {type: str}
  filename: {type: str}
  """)


class Packages(Descriptor):
    """Object representing Pakcages

    Args:
      descriptor - yaml containing Packages section
    """
    def __init__(self, descriptor, descriptor_path):
        self.schemas = packages_schema
        self.descriptor_path = descriptor_path
        super(Packages, self).__init__(descriptor)
        if ('content_sets_file' in descriptor and 'content_sets' in descriptor):
            raise CekitError("You cannot specify content_sets and content_sets_file together!")

        if 'content_sets_file' in descriptor:
            content_sets_file = os.path.join(self.descriptor_path, descriptor['content_sets_file'])

            if not os.path.exists(content_sets_file):
                raise CekitError("'%s' file not found!" % content_sets_file)

            with open(content_sets_file, 'r') as file_:
                descriptor['content_sets'] = yaml.safe_load(file_)
            del descriptor['content_sets_file']

        self._prepare()

    def _prepare(self):
        self._descriptor['repositories'] = [Repository(x)
                                            for x in self._descriptor.get('repositories', [])]

    @property
    def repositories(self):
        return self.get('repositories', [])

    @property
    def install(self):
        return self.get('install', [])

    @property
    def content_sets(self):
        return self.get('content_sets')

    @content_sets.setter
    def content_sets(self, value):
        self._descriptor['content_sets'] = value
        self._descriptor.pop('content_sets_file', None)

    @property
    def content_sets_file(self):
        return self.get('content_sets_file')

    @content_sets_file.setter
    def content_sets_file(self, value):
        self._descriptor['content_sets_file'] = value
        self._descriptor.pop('content_sets', None)

class Repository(Descriptor):
    """Object representing package repository

    Args:
      descriptor - repository name as referenced in cekit config file
    """

    def __init__(self, descriptor):
        # we test parameter is not dict as there is no easy way how to test
        # if something is string both in py2 and py3
        if not isinstance(descriptor, dict):
            descriptor = self._create_repo_object(descriptor)

        if 'filename' not in descriptor:
            descriptor['filename'] = '%s.repo' % descriptor['name'].replace(' ', '_')

        if not (('url' in descriptor) ^
                ('odcs' in descriptor) ^
                ('id' in descriptor) ^
                ('rpm' in descriptor)):
            raise CekitError("Repository '%s' is invalid, you can use only one of "
                             "['id', 'odcs', 'rpm', 'url']"
                             % descriptor['name'])

        if 'url' not in descriptor:
            descriptor['url'] = {}


        self.schemas = [repository_schema]
        super(Repository, self).__init__(descriptor)

        # we dont want to merge any of theese
        self.skip_merging = ['rpm',
                             'id',
                             'url']

        if 'present' not in self._descriptor:
            self._descriptor['present'] = True

    def _create_repo_object(self, repository):
        logger.warning("The way of defining repository '%s' is deprecated. Convert "
                       "it to an URL based repository object. Consult Cekit docs, "
                       "for more details." % repository)
        descriptor = {}
        descriptor['name'] = repository
        descriptor['url'] = {}
        descriptor['url']['repository'] = self._get_repo_url(descriptor)
        return descriptor

    def _get_repo_url(self, descriptor):
        """Retruns repository url from Cekit config files repositories section"""
        configured_repositories = config.get('repositories')

        # We need to remove the custom "__name__" element before we can show
        # which repository keys are defined in the configuration
        configured_repository_names = configured_repositories.keys()

        if '__name__' in configured_repository_names:
            configured_repository_names.remove('__name__')

        if descriptor['name'] not in configured_repositories:
            if len(configured_repository_names):
                logger.warning("Package repository '%s' used in descriptor is not "
                                 "available in Cekit configuration file. "
                                 "Available repositories: %s"
                                 % (descriptor['name'], ' '.join(configured_repository_names)))
            else:
                logger.warning("Package repository '%s' used in descriptor is not "
                                 "available in Cekit configuration file. "
                                 % descriptor['name'])
            return None

        return configured_repositories[descriptor['name']]

    def fetch(self, target_dir):
        if not self._descriptor['url']['repository']:
            raise CekitError("Repository not defined for '%s'." % (self.name))
        if not os.path.exists(target_dir):
                os.makedirs(target_dir)
        Resource({'url': self._descriptor['url']['repository']}) \
            .copy(os.path.join(target_dir, self._descriptor['filename']))

    @property
    def name(self):
        return self.get('name')

    @name.setter
    def name(self, value):
        self._descriptor['name'] = value

    @property
    def description(self):
        return self.get('description')

    @description.setter
    def description(self, value):
        self._descriptor['description'] = value

    @property
    def present(self):
        return self.get('present', True)

    @present.setter
    def present(self, value):
        self._descriptor['present'] = value

    @property
    def id(self):
        return self.get('id')

    @id.setter
    def id(self, value):
        self._descriptor['id'] = value
        self._descriptor.pop('url', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('odcs', None)
        self._descriptor.pop('filename', None)

    @property
    def url(self):
        return self.get('url')

    @url.setter
    def url(self, value):
        self._descriptor['url'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('odcs', None)
        self._descriptor.pop('filename', None)

    @property
    def rpm(self):
        return self.get('rpm')

    @rpm.setter
    def rpm(self, value):
        self._descriptor['rpm'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('url', None)
        self._descriptor.pop('odcs', None)
        self._descriptor.pop('filename', None)

    @property
    def odcs(self):
        return self.get('odcs')

    @odcs.setter
    def odcs(self, value):
        self._descriptor['odcs'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('url', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('filename', None)

    @property
    def filename(self):
        return self.get('filename')

    @filename.setter
    def filename(self, value):
        self._descriptor['filename'] = value
        self._descriptor.pop('id', None)
        self._descriptor.pop('url', None)
        self._descriptor.pop('rpm', None)
        self._descriptor.pop('odcs', None)

# coding=utf-8
# Copyright 2024 The TensorFlow Datasets Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
from unittest import mock

from absl.testing import flagsaver
from etils import epath
import pytest
from tensorflow_datasets import testing
from tensorflow_datasets.core import constants
from tensorflow_datasets.core import naming
from tensorflow_datasets.core.utils import file_utils
from tensorflow_datasets.core.utils import read_config

_DATA_DIR = epath.Path('/a')
_DATASET_NAME = 'my_ds'
_DATASET_DIR = _DATA_DIR / _DATASET_NAME


def test_default_data_dir():
  data_dir = file_utils.get_default_data_dir(given_data_dir=None)
  assert data_dir


def _add_dataset_info(mock_fs: testing.MockFs, dataset_dir: epath.Path) -> None:
  mock_fs.add_file(dataset_dir / constants.DATASET_INFO_FILENAME)


def _add_features(
    mock_fs: testing.MockFs, dataset_dir: epath.Path, content: str = None
) -> None:
  mock_fs.add_file(dataset_dir / constants.FEATURES_FILENAME, content=content)


def test_list_dataset_variants_with_configs(mock_fs: testing.MockFs):
  configs_and_versions = {
      'x': ['1.0.0', '1.0.1'],
      'y': ['2.0.0'],
  }
  info_filenames = {
      constants.FEATURES_FILENAME,
      constants.DATASET_INFO_FILENAME,
  }
  glob_suffixes = [
      'json',
  ]
  for config, versions in configs_and_versions.items():
    for version in versions:
      for info_filename in info_filenames:
        mock_fs.add_file(_DATASET_DIR / config / version / info_filename)

  references = sorted(
      file_utils.list_dataset_variants(
          dataset_dir=_DATASET_DIR, glob_suffixes=glob_suffixes
      )
  )
  assert references == [
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          config='x',
          version='1.0.0',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          config='x',
          version='1.0.1',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          config='y',
          version='2.0.0',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
  ]


def test_list_dataset_variants_with_configs_no_versions(
    mock_fs: testing.MockFs,
):
  configs_and_versions = {
      'x': ['1.0.0', '1.0.1'],
      'y': ['2.0.0'],
  }
  info_filenames = {
      constants.DATASET_INFO_FILENAME,
      constants.FEATURES_FILENAME,
  }
  for config, versions in configs_and_versions.items():
    for version in versions:
      for filename in info_filenames:
        mock_fs.add_file(_DATASET_DIR / config / version / filename)

  references = sorted(
      file_utils.list_dataset_variants(
          dataset_dir=_DATASET_DIR, include_versions=False
      )
  )
  assert references == [
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          config='x',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          config='y',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
  ]


def test_list_dataset_variants_without_configs(mock_fs: testing.MockFs):
  # Version 1.0.0 doesn't have features.json, because it was generated with an
  # old version of TFDS.
  _add_dataset_info(mock_fs, _DATASET_DIR / '1.0.0')
  _add_dataset_info(mock_fs, _DATASET_DIR / '1.0.1')
  _add_features(mock_fs, _DATASET_DIR / '1.0.1')

  # List dirs including datasets generated by old TFDS versions.
  references = sorted(
      file_utils.list_dataset_variants(
          dataset_dir=_DATASET_DIR,
          include_versions=True,
          include_old_tfds_version=True,
      )
  )
  assert references == [
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          version='1.0.0',
          data_dir=_DATA_DIR,
          info_filenames={constants.DATASET_INFO_FILENAME},
      ),
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          version='1.0.1',
          data_dir=_DATA_DIR,
          info_filenames={
              constants.DATASET_INFO_FILENAME,
              constants.FEATURES_FILENAME,
          },
      ),
  ]

  # List dirs excluding datasets generated by old TFDS versions.
  references = sorted(
      file_utils.list_dataset_variants(
          dataset_dir=_DATASET_DIR,
          include_versions=True,
          include_old_tfds_version=False,
      )
  )
  assert references == [
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          version='1.0.1',
          data_dir=_DATA_DIR,
          info_filenames={
              constants.DATASET_INFO_FILENAME,
              constants.FEATURES_FILENAME,
          },
      )
  ]


def test_list_datasets_in_data_dir(mock_fs: testing.MockFs):
  _add_dataset_info(mock_fs, _DATA_DIR / 'ds1' / 'config1' / '1.0.0')
  _add_features(mock_fs, _DATA_DIR / 'ds1' / 'config1' / '1.0.0')
  _add_dataset_info(mock_fs, _DATA_DIR / 'ds1' / 'config1' / '2.0.0')
  _add_features(mock_fs, _DATA_DIR / 'ds1' / 'config1' / '2.0.0')
  _add_dataset_info(mock_fs, _DATA_DIR / 'ds1' / 'config2' / '1.0.0')
  _add_features(mock_fs, _DATA_DIR / 'ds1' / 'config2' / '1.0.0')

  _add_dataset_info(mock_fs, _DATA_DIR / 'ds2' / '1.0.0')
  _add_features(mock_fs, _DATA_DIR / 'ds2' / '1.0.0')

  info_filenames = {
      constants.DATASET_INFO_FILENAME,
      constants.FEATURES_FILENAME,
  }

  # The following are problematic and should thus be ignored.
  _add_features(mock_fs, _DATA_DIR / 'invalid-name' / '1.0.0', content='x')
  _add_features(mock_fs, _DATA_DIR / 'invalid_version1' / '1.a.b', content='x')
  _add_features(
      mock_fs, _DATA_DIR / 'invalid_version2' / '1.2.3.4', content='x'
  )

  references = sorted(file_utils.list_datasets_in_data_dir(data_dir=_DATA_DIR))
  assert references == [
      naming.DatasetReference(
          dataset_name='ds1',
          config='config1',
          version='1.0.0',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
      naming.DatasetReference(
          dataset_name='ds1',
          config='config1',
          version='2.0.0',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
      naming.DatasetReference(
          dataset_name='ds1',
          config='config2',
          version='1.0.0',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
      naming.DatasetReference(
          dataset_name='ds2',
          version='1.0.0',
          data_dir=_DATA_DIR,
          info_filenames=info_filenames,
      ),
  ]


def test_list_datasets_in_data_dir_with_namespace(mock_fs: testing.MockFs):
  namespace = 'ns'
  _add_dataset_info(mock_fs, _DATASET_DIR / 'config1' / '1.0.0')
  _add_features(mock_fs, _DATASET_DIR / 'config1' / '1.0.0')

  references = sorted(
      file_utils.list_datasets_in_data_dir(
          data_dir=_DATA_DIR,
          namespace=namespace,
          include_configs=True,
          include_versions=True,
      )
  )

  assert references == [
      naming.DatasetReference(
          dataset_name=_DATASET_NAME,
          namespace=namespace,
          config='config1',
          version='1.0.0',
          data_dir=_DATA_DIR,
          info_filenames={
              constants.DATASET_INFO_FILENAME,
              constants.FEATURES_FILENAME,
          },
      ),
  ]


def test_find_files_without_glob(mock_fs: testing.MockFs):
  folder = epath.Path('/')
  mock_fs.add_file(folder / 'a' / 'b' / 'x')
  mock_fs.add_file(folder / 'a' / 'c' / 'x')
  mock_fs.add_file(folder / 'b' / 'd' / 'x')
  mock_fs.add_file(folder / 'b' / 'd' / 'y')  # Should be ignored.
  mock_fs.add_file(folder / 'b' / '.config' / 'x')  # Should be ignored.
  mock_fs.add_file(folder / 'b' / 'x')
  mock_fs.add_file(folder / 'b' / 'y')  # Should be ignored.
  actual = file_utils._find_files_without_glob(
      folder, globs=['*/*', '*/*/*'], file_names=['x']
  )
  actual = [os.fspath(p) for p in actual]
  assert sorted(actual) == ['/a/b/x', '/a/c/x', '/b/d/x', '/b/x']


@pytest.mark.parametrize(
    ['filename', 'result'],
    [
        ('abc', False),
        (constants.DATASET_INFO_FILENAME, True),
        (constants.FEATURES_FILENAME, True),
        ('mnist-test.tfrecord-00000-of-00001', True),
        ('mnist-test.arrayrecord-00000-of-00001', True),
    ],
)
def test_looks_like_a_tfds_file(filename, result):
  assert file_utils._looks_like_a_tfds_file(filename) == result


@pytest.mark.parametrize(
    ['path', 'glob_result', 'expected'],
    [
        ('/a/*', ['/a/b', '/a/c'], ['/a/b', '/a/c']),
        ('/a/b', None, ['/a/b']),
        ('a/*', None, ['a/*']),
        ('/a/b@*', None, ['/a/b@*']),
    ],
)
def test_expand_glob(path, glob_result, expected):
  with mock.patch.object(epath, 'Path') as mock_epath:
    mock_epath.return_value.expanduser.return_value = path
    mock_epath.return_value.glob.return_value = glob_result
    actual = file_utils.expand_glob(path)
    if glob_result is not None:
      mock_epath.return_value.glob.assert_called_once_with(path[1:])
    else:
      mock_epath.return_value.glob.assert_not_called()
    actual = [os.fspath(p) for p in actual]
    assert actual == expected


def test_publish_data(mock_fs: testing.MockFs):
  from_data_dir = epath.Path('/tmp') / 'dummy_mnist/3.0.1'
  filename = constants.DATASET_INFO_FILENAME
  content = 'a'
  mock_fs.add_file(path=from_data_dir / filename, content=content)
  to_data_dir = epath.Path('/a/b')
  file_utils.publish_data(from_data_dir=from_data_dir, to_data_dir=to_data_dir)
  assert mock_fs.read_file(to_data_dir / filename) == content


if __name__ == '__main__':
  testing.test_main()

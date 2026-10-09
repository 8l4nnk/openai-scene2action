import pytest
from isaac.normal_baseline.runtime_version import version_from_file


def test_binary_container_version_file_is_reported_without_inventing_wheel_metadata(tmp_path):
    p=tmp_path/'VERSION';p.write_text('6.1.0+build.42\n',encoding='utf-8')
    assert version_from_file(p)=={'version':'6.1.0+build.42','source':'binary_VERSION'}


def test_official_container_prerelease_and_build_are_preserved(tmp_path):
    p=tmp_path/'VERSION'
    value='6.1.0-rc.26+release.49347.2d230af4.gl'
    p.write_text(value,encoding='utf-8')
    assert version_from_file(p)=={'version':value,'source':'binary_VERSION'}


@pytest.mark.parametrize('text',['5.1.0','6.1.01','unknown','6.1.0\n5.1.0'])
def test_wrong_or_ambiguous_runtime_version_is_rejected(tmp_path,text):
    p=tmp_path/'VERSION';p.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError): version_from_file(p)

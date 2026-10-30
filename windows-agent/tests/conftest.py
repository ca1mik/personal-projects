import pytest
from localagent.power import Power

@pytest.fixture(autouse=True)
def no_real_os_power_in_unit_tests(monkeypatch):
    async def forbidden(self,args):
        raise AssertionError('Unit tests must replace Power.run; live shutdown is forbidden in pytest')
    monkeypatch.setattr(Power,'run',forbidden)

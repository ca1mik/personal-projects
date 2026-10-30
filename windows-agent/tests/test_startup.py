from startup_chain import vpn_active
import subprocess
from pathlib import Path
import pytest
import startup_chain

def test_startup_waits_for_real_tunnel_routes():
    assert not vpn_active({'adapters':[]})
    assert not vpn_active({'adapters':[{'up':True,'routes':['172.19.0.0/30']}]})
    assert not vpn_active({'adapters':[{'up':False,'routes':['0.0.0.0/0']}]})
    assert vpn_active({'adapters':[{'up':True,'routes':['0.0.0.0/0']}]})
    assert vpn_active({'adapters':[{'up':True,'routes':['0.0.0.0/1','128.0.0.0/1']}]})
    assert not vpn_active({'adapters':[{'up':True,'routes':['0.0.0.0/1']}]})

def test_registered_updated_package_resolves_without_windowsapps_enumeration(tmp_path,monkeypatch):
    package=tmp_path/'new-version';exe=package/'app/ChatGPT.exe';exe.parent.mkdir(parents=True);exe.touch()
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,0,(str(package)+'\r\n').encode('utf-8'),b''))
    monkeypatch.setattr(Path,'glob',lambda *a: (_ for _ in ()).throw(PermissionError('WindowsApps not enumerable')))
    assert startup_chain.desktop_executable({'codex_exe':str(tmp_path/'removed-old.exe')})==exe

def test_configured_desktop_survives_package_query_failure(tmp_path,monkeypatch):
    exe=tmp_path/'ChatGPT.exe';exe.touch()
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,1,b'',b'query failed'))
    assert startup_chain.desktop_executable({'codex_exe':str(exe)})==exe

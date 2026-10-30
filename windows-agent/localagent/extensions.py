"""Explicitly enabled local extensions, pinned by source hash. No remote auto-installation."""
import hashlib,importlib.util,json
from .base import ROOT,config,inside

class Extensions:
    def __init__(self):
        self.handlers={};self.instructions=[]
        for entry in config().get('extensions',[]):
            path=inside(ROOT/'extensions',entry['file'])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
                raise RuntimeError('Extension hash changed; review source before enabling: '+path.name)
            spec=importlib.util.spec_from_file_location('localagent_ext_'+path.stem,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            for name,tool in module.TOOLS.items():
                if not name.startswith('ext_') or name in self.handlers:raise ValueError('Extension tool names must be unique and start with ext_')
                self.handlers[name]=tool['handler']
                self.instructions.append(name+': '+tool['description']+' (requires owner approval)')
    async def execute(self,name,tid,args,context):
        return await self.handlers[name](tid,args,context)

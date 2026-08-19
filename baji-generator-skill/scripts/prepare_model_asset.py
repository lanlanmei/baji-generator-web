"""Assign the supplied master OBJ to the three stable material regions."""
from pathlib import Path

ROOT=Path(__file__).parents[1]
OBJ=ROOT/'assets'/'models'/'badge_master_58mm.obj'
FRONT_FACES=45824
FRONT_ART_FACES=44800

def prepare(path=OBJ):
    path=Path(path); lines=path.read_text(encoding='utf-8').splitlines(); out=[]; shell_face=0; in_shell=False
    for line in lines:
        if line.startswith('g '):
            name=line.split(maxsplit=1)[1]; in_shell=name=='badge_shell'
            if in_shell:
                out.extend(('g front_art','usemtl front_art')); shell_face=0
            else:
                out.extend((line,'usemtl back_metal'))
            continue
        if line.startswith('usemtl '): continue
        if in_shell and line.startswith('f '):
            if shell_face==FRONT_ART_FACES: out.extend(('g rim_metal','usemtl rim_metal'))
            if shell_face==FRONT_FACES: out.extend(('g back_shell','usemtl back_metal'))
            shell_face+=1
        out.append(line)
    path.write_text('\n'.join(out)+'\n',encoding='utf-8',newline='\n')
    return path

if __name__=='__main__': print(prepare())

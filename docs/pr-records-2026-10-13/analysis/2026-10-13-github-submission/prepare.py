from pathlib import Path
import subprocess,json,shutil
root=Path('/home/jooheon/C4_500');out=root/'analysis/2026-10-13-github-submission';repo='/home/jooheon/carrotpilot-ms';base='b98d5053e224ae0d0e419d096c70ce110511a1d6';patchdir=root/'docs/pr-submission-261013'
patches={k:patchdir/v for k,v in {'A':'rebuild_all-A-626b887d.patch','B':'scons_cache_guard-B-626b887d.patch','D':'startup-touch-D-626b887d-v2.patch'}.items()}
paths={k:[s[6:] for s in p.read_text().splitlines() if s.startswith('+++ b/')] for k,p in patches.items()}
allpaths=set(sum(paths.values(),[]));original={};modes={}
for name in allpaths:
 r=subprocess.run(['git','-C',repo,'show',base+':'+name],capture_output=True)
 if r.returncode==0:
  original[name]=r.stdout
  mode=subprocess.check_output(['git','-C',repo,'ls-tree',base,'--',name],text=True).split()[0];modes[name]=mode
 else:modes[name]='100644'
for variant,order in [('A',['A']),('AB',['A','B']),('D',['D'])]:
 work=out/('source-'+variant);assert not work.exists();work.mkdir()
 subprocess.run(['git','init','-q',str(work)],check=True)
 for name,data in original.items():
  f=work/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data);f.chmod(0o755 if modes[name]=='100755' else 0o644)
 for k in order:
  subprocess.run(['git','apply','--check',str(patches[k])],cwd=work,check=True)
  subprocess.run(['git','apply',str(patches[k])],cwd=work,check=True)
 publish=sorted(set(sum([paths[k] for k in order],[])))
 entries=[{'path':name,'mode':modes[name],'type':'blob','content':(work/name).read_text()} for name in publish]
 (out/(variant+'-tree.json')).write_text(json.dumps(entries))
 print(variant,len(entries),'files',sum(len(e['content']) for e in entries),'characters')
(out/'base.json').write_text(json.dumps({'repository':'ajouatom/openpilot','base_branch':'carrot-wip','base_sha':base,'base_tree':'579ee54105300f18fd47270008725232554e15a0','fork':'chant555/carrot-wip-BRH','checks':'patch applicability only; no additional runtime or device tests'},indent=2)+'\n')

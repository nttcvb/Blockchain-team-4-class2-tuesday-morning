import argparse
import json
from pathlib import Path
from .config import ScenarioConfig, load_params


def main():
    parser=argparse.ArgumentParser(description='Terra run laboratory')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare')
    cal=sub.add_parser('calibrate'); cal.add_argument('--generations',type=int,default=12); cal.add_argument('--popsize',type=int,default=4); cal.add_argument('--split',choices=['train','all'],default='train')
    run=sub.add_parser('run'); run.add_argument('--scenario',default='historical'); run.add_argument('--config'); run.add_argument('--seed',type=int,default=42); run.add_argument('--deterministic',action='store_true'); run.add_argument('--stress-days',type=int,default=7)
    suite=sub.add_parser('suite'); suite.add_argument('--seeds',type=int,default=20); suite.add_argument('--scenarios',nargs='*'); suite.add_argument('--stress-days',type=int,default=7); suite.add_argument('--resume',action='store_true')
    sub.add_parser('sensitivity'); sub.add_parser('timestep-check'); sub.add_parser('report'); sub.add_parser('audit'); sub.add_parser('diagnostics')
    args=parser.parse_args()
    if args.command=='prepare':
        from .data import prepare
        result=prepare()
    elif args.command=='calibrate':
        from .calibrate import calibrate
        result=calibrate(args.generations,args.popsize,args.split)
    elif args.command=='run':
        from .engine import simulate
        from .experiments import scenario_presets,export_run
        from dataclasses import replace
        c=ScenarioConfig.from_dict(json.loads(Path(args.config).read_text(encoding='utf-8'))) if args.config else scenario_presets(stress_days=args.stress_days)[args.scenario]
        c=replace(c,seed=args.seed,stochastic=not args.deterministic)
        t,m,l=simulate(c); export_run(c,t,m,l); result=m
    elif args.command=='suite':
        from .experiments import run_suite
        result=run_suite(args.seeds,args.scenarios,stress_days=args.stress_days,resume=args.resume).to_dict()
    elif args.command=='sensitivity':
        from .experiments import sensitivity
        result=sensitivity().to_dict()
    elif args.command=='timestep-check':
        from .experiments import timestep_check
        result=timestep_check()
    elif args.command=='audit':
        from .audit import audit_outputs
        result=audit_outputs()
    elif args.command=='diagnostics':
        from .diagnostics import build_diagnostics
        result=build_diagnostics()
    else:
        from .report import build_report
        result={'report':str(build_report())}
    print(json.dumps(result,ensure_ascii=True,indent=2,default=str))


if __name__=='__main__': main()

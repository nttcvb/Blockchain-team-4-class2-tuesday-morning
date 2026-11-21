import argparse
import json
from pathlib import Path
from .config import ScenarioConfig, load_params


def main():
    parser=argparse.ArgumentParser(description='Terra run laboratory')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare')
    cal=sub.add_parser('calibrate'); cal.add_argument('--generations',type=int,default=12); cal.add_argument('--popsize',type=int,default=4); cal.add_argument('--split',choices=['train','all'],default='train')
    cal.add_argument('--workers',type=int,default=1,help='Parallel candidate evaluators; start with 2 on Windows')
    cal.add_argument('--population',type=int,default=1000,help='Depositor population used for fitting and final validation')
    cal.add_argument('--refinement-iterations',type=int,help='Local iterations after broad search; 0 disables refinement')
    cal.add_argument('--seed',type=int,default=42,help='Optimizer seed; model calibration stays deterministic')
    cal.add_argument('--warm-start',help='JSON with named parameters, not a positional search vector')
    cal.add_argument('--no-resume',action='store_true',help='Ignore exact checkpoint; parameter files still provide named warm starts')
    run=sub.add_parser('run'); run.add_argument('--scenario',default='historical'); run.add_argument('--config'); run.add_argument('--seed',type=int,default=42); run.add_argument('--deterministic',action='store_true'); run.add_argument('--stress-days',type=int,default=7)
    suite=sub.add_parser('suite'); suite.add_argument('--seeds',type=int,default=20); suite.add_argument('--scenarios',nargs='*'); suite.add_argument('--stress-days',type=int,default=7); suite.add_argument('--resume',action='store_true')
    sub.add_parser('sensitivity'); sub.add_parser('timestep-check'); sub.add_parser('report'); sub.add_parser('audit'); sub.add_parser('diagnostics')
    sub.add_parser('reconstruction-report',help='Audited historical reconstruction charts and report; no policy suite required')
    checks=sub.add_parser('reconstruction-check',help='Historical cadCAD seed and time-step checks; no policy suite required')
    checks.add_argument('--seeds',type=int,default=20)
    args=parser.parse_args()
    if args.command=='prepare':
        from .data import prepare
        result=prepare()
    elif args.command=='calibrate':
        from .calibrate import calibrate
        result=calibrate(args.generations,args.popsize,args.split,population=args.population,
                         resume=not args.no_resume,workers=args.workers,
                         refinement_iterations=args.refinement_iterations,seed=args.seed,
                         warm_start=args.warm_start)
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
    elif args.command=='reconstruction-report':
        from .reconstruction import build_reconstruction_report
        result=build_reconstruction_report()
    elif args.command=='reconstruction-check':
        from .reconstruction_validation import run_reconstruction_checks
        result=run_reconstruction_checks(args.seeds)
    else:
        from .report import build_report
        result={'report':str(build_report())}
    print(json.dumps(result,ensure_ascii=True,indent=2,default=str))


if __name__=='__main__': main()

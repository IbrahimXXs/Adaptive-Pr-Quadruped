"""One entry point for experiments, analysis, and the recording catalog."""

import argparse
import importlib


COMMANDS = {
    "pad": ("experiments.pad", "Run a blind landing trial on an adjustable pad"),
    "pad-study": ("experiments.pad_study", "Collect demonstrations, train PRIMP, and compare planners"),
    "analyze-pad": ("analysis.pad", "Analyze an adjustable-pad recording"),
    "replay": ("visualization.replay", "Render a recorded pad trial without rerunning the controller"),
    "standing": ("experiments.standing", "Record four-foot standing on flat ground"),
    "step": ("experiments.step", "Run coordinated front-left steps with contact-confirmed landing"),
    "analyze-standing": ("analysis.standing", "Analyze an existing standing recording"),
    "analyze-step": ("analysis.step", "Analyze an existing controlled-step recording"),
    "results": ("recording.catalog", "Refresh and list the recording catalog"),
}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m primp_project", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, (_, description) in COMMANDS.items():
        commands.add_parser(name, add_help=name == "results", help=description, description=description)
    args, remaining = parser.parse_known_args(argv)
    module = importlib.import_module(f"primp_project.{COMMANDS[args.command][0]}")
    if args.command == "results":
        if remaining:
            parser.error("results takes no additional arguments")
        return module.list_results()
    return module.main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())

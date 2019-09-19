import eneel.load_runner as load_runner
import argparse
import eneel.logger as logger
logger = logger.get_logger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', help='The name of the project (i.e my_project for project.yml)')
    parser.add_argument('--connections', help='Optinally add the full path to connections.yml')
#    parser.add_argument('--logdir', help='For not using the default log directory')
    args = parser.parse_args()

    if not args.project:
        logger.error("You need to supply your project name. I.e my_project to use my_project.yml")

#    if not args.connections:
#        logger.error("You need to supply a path to your connections.yml")

    else:
#        logger.info("Connections config: " + args.connections)
        logger.info("Loading project: " + args.project)
        try:
            load_runner.run_project(args.project, args.connections)
        except KeyboardInterrupt:
            logger.warning("Interupted by user")


if __name__ == '__main__':
    main()


import argparse
from workforce.db import make_engine, sessions
from workforce.service import Service

def main():
    parser = argparse.ArgumentParser(description="Eenmalige lokale platformbeheerder-bootstrap")
    parser.add_argument("--email", required=True, help="Reeds geregistreerd persoonlijk account")
    args = parser.parse_args()
    Service(sessions(make_engine())).bootstrap(args.email)
    print("Platformbeheerder ingesteld. Bootstrap is nu gesloten.")

if __name__ == "__main__":
    main()

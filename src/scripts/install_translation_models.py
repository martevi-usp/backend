"""Downloads and installs the Argos Translate language packages this backend
needs (en<->pt) so the running container never needs network access for
translation at request time — see ADR-0002.

Run once, at Docker build time (backend/Dockerfile's `base` stage), not at
container startup or on first request. Needs network access itself (to fetch
the package index and the model files); the point is that the *running
server* never does.
"""

import argostranslate.package as package
import argostranslate.translate as translate

LANGUAGE_PAIRS = [("en", "pt"), ("pt", "en")]


def main() -> None:
    package.update_package_index()
    available = package.get_available_packages()
    by_pair = {(p.from_code, p.to_code): p for p in available}

    missing = [pair for pair in LANGUAGE_PAIRS if pair not in by_pair]
    if missing:
        raise SystemExit(
            f"Argos Translate package index has no package for: {missing} "
            f"— check https://raw.githubusercontent.com/argosopentech/argospm-index/main/ "
            f"for current availability before changing LANGUAGE_PAIRS."
        )

    for pair in LANGUAGE_PAIRS:
        pkg = by_pair[pair]
        print(
            f"Installing Argos Translate package {pair[0]} -> {pair[1]} "
            f"(v{pkg.package_version})..."
        )
        downloaded_path = pkg.download()
        package.install_from_path(downloaded_path)

    # One real translate() per direction, while this build step still has
    # network access: Argos's sentence-boundary detector (MiniSBD) fetches its
    # model lazily on first use, so this bakes it into the image and lets the
    # running container stay offline (ADR-0005).
    for source, target in LANGUAGE_PAIRS:
        print(f"Warming up sentence-boundary-detector for {source} -> {target}...")
        sample = translate.translate("Sunflowers", source, target)
        print(f"  {source} -> {target} sample translation: {sample!r}")

    print("Done — installed:", package.get_installed_packages())


if __name__ == "__main__":
    main()

"""PROTOTYPE: render every layout variant x fixture through LaraPaper as the TRMNL X sees it.

    python screens/media/prototype/render.py [variant-glob] [fixture-name ...]

Uses the LaraPaper container's own renderer and the first device's model, without
saving anything: the What to Watch plugin is loaded, given the variant markup and
fixture data in memory, and rendered. PNGs land in out/, plus out/index.html.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import fixtures

HERE = Path(__file__).parent
OUT = Path(os.environ.get("PROTOTYPE_OUT", HERE / "out"))
CONTAINER = "larapaper"
WORK = "/tmp/media-prototype"

PHP = r'''
$jobs = json_decode(file_get_contents("WORK/jobs.json"), true);
$p = App\Models\Plugin::where("name", "What to Watch")->firstOrFail();
$d = App\Models\Device::firstOrFail();
$dir = storage_path("app/public/images/generated");
foreach ($jobs as $j) {
    $p->render_markup = file_get_contents("WORK/" . $j["markup"]);
    $p->data_payload = json_decode(file_get_contents("WORK/" . $j["data"]), true);
    try {
        $id = App\Services\ImageGenerationService::generateImageFromModel($p->render("full", true, $d), $d->deviceModel, $p->user, null, $d, $p);
        rename("$dir/$id.png", "WORK/out/" . $j["name"] . ".png");
        echo "ok " . $j["name"] . "\n";
    } catch (Throwable $e) {
        echo "FAIL " . $j["name"] . ": " . $e->getMessage() . "\n";
    }
}
'''.replace("WORK", WORK)


def sh(*args, **kw):
    return subprocess.run(args, check=True, text=True, **kw)


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "*"
    wanted = set(sys.argv[2:])
    variants = sorted((HERE / "variants").glob(f"{pattern}.liquid"))
    fx = {k: v for k, v in fixtures.variants().items() if not wanted or k in wanted}

    stage = HERE / "out" / ".stage"
    stage.mkdir(parents=True, exist_ok=True)
    jobs = []
    for name, data in fx.items():
        (stage / f"{name}.json").write_text(json.dumps(data))
    for v in variants:
        (stage / v.name).write_text(v.read_text())
        for name in fx:
            jobs.append({"name": f"{v.stem}__{name}", "markup": v.name, "data": f"{name}.json"})
    (stage / "jobs.json").write_text(json.dumps(jobs))

    sh("docker", "exec", "-u", "root", CONTAINER, "rm", "-rf", WORK)
    sh("docker", "cp", f"{stage}/.", f"{CONTAINER}:{WORK}")
    # docker cp writes as root; the PHP process runs as the web user.
    sh("docker", "exec", "-u", "root", CONTAINER, "sh", "-c", f"mkdir -p {WORK}/out && chown -R $(stat -c %u:%g /var/www/html/storage) {WORK}")
    r = subprocess.run(["docker", "exec", CONTAINER, "php", "/var/www/html/artisan", "tinker", "--execute", PHP],
                       text=True, capture_output=True)
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("ok ", "FAIL "))) or r.stdout[-2000:] + r.stderr[-2000:])
    sh("docker", "cp", f"{CONTAINER}:{WORK}/out/.", str(OUT))
    sh("docker", "exec", "-u", "root", CONTAINER, "rm", "-rf", WORK)


if __name__ == "__main__":
    main()

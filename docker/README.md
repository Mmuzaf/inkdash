# Running the renderer in Docker

Three files, for two quite different jobs:

| File | Purpose |
| --- | --- |
| [Dockerfile](Dockerfile) | The image. Python 3.12 slim, dependencies installed with uv from the lockfile |
| [docker-compose.yml](docker-compose.yml) | Local container, built from the source tree |
| [casaos.yml](casaos.yml) | The same service as a CasaOS app, installed from a published image |

## Locally

```bash
make docker-build
make docker-up                # http://localhost:10825/render/home.png
make docker-logs
make docker-down
make docker-up PORT=9000      # default is 10825
```

## CasaOS

[casaos.yml](casaos.yml) is the same service in the format CasaOS expects: `x-casaos`
metadata, a `/DATA/AppData` bind mount, and a description for every port, volume and
environment variable so the install screen is filled in rather than blank.

CasaOS installs an app by pulling an image and cannot build one, so publish it first:

```bash
docker login
make docker-release IMAGE=<your docker hub user>/inkdash
```

Then paste `casaos.yml` into **App Store > Custom Install**, with the `image:` line
pointing at what you just pushed.

### Verify

```bash
curl -sS http://localhost:10825/health
curl -sS http://192.168.88.115:10825/health
```

```bash
curl -sS -o /tmp/home.png http://192.168.88.115:10825/render/home.png && open /tmp/home.png
curl -sSI http://192.168.88.115:10825/render/home.png | grep -i etag
curl -sS http://192.168.88.115:10825/render/home.txt
```
# mitm chrome

Integrate chrome with [mitmproxy](https://mitmproxy.org/).

## installation

```shell
git clone https://github.com/linw1995/mitm_chrome.git
pip install ./mitm_chrome
```

## Usage

On MacOS

```shell
mitm_chrome --chrome-path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' mitmproxy
```

Else

```shell
mitm_chrome mitmproxy
```

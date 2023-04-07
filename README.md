# vodafone-router-host-table

A cli tool to show the connected devices to a Vodafone Germany cable internet
router.

## About

Vodafone Germany provides a modem for connecting to their cable internet. This
modem has a typical web ui for administration that shows device information and
can list the connected devices and their IP addresses.

<p align="center">
<a href="./docs/router.png"><img src="./docs/thumbnail_router.png"></a>
&nbsp;
<a href="./docs/webui.png"><img src="./docs/thumbnail_webui.png"></a>
</p>

It can be useful to programatically access the list of devices attached to the
router via scripts or cli to do automations or to simply access the data faster
than via the web ui.

The web ui is not trivially scrapable as significant portions are populated by
javascript and protected by a login mechanism and even some security heuristics
looking at the page loading network requests. This adds some hurdles to
accessing the data.

This repository ships a simple Python script that can scrape the list of
connected devices to a router.

It works by connecting to the router specified (defaulting to 192.168.0.1) and
logs in with a specified admin username (defaulting to admin) and password
(mandatory to set via environment variable). It then fetches a some pages from
the web ui to fool the router security heuristics into thinking it's a typical
browser before finally fetching the host table data and displaying it to the
stdout.

Example output:

```
$ ROUTER_PASSWORD=<your-password> python3 get-host-table.py
Alias             | IP Address    | MAC Address
----------------- | ------------- | -----------------
michael-laptop    | 192.168.0.4   | c4:86:08:aa:c4:59
08:33:88:5d:ee:2a | 192.168.0.241 | 08:33:88:5d:ee:2a
ac:80:47:c0:f0:b7 | 192.168.0.23  | ac:80:47:c0:f0:b7
60:6a:ff:ef:ab:a1 | 192.168.0.113 | 60:6a:ff:ef:ab:a1
b4:f0:da:b6:48:c2 | 192.168.0.200 | b4:f0:da:b6:48:c2
001788a28ffb      | 192.168.0.133 | 00:1a:88:a2:8f:fb
amazon-73088b822  | 192.168.0.110 | 3c:5f:c4:87:ae:00
```

## Installation

The script depends on Python3 and the python module [pbkdf2][1]. You can
install the python module via pip.

```
pip3 install pbkdf2
```

For installing the script itself, you can simply copy the Python script to your
desired path to install. Putting it into your PATH environment is the most
trivial location to make it easy to execute.

## Usage

To use the script you must set the environment variable ROUTER_PASSWORD to
contain the router password and then execute the Python script:
`get-host-table.py`.

By default it connects to the router at `192.168.0.1`. You can change the IP
address by passing the parameter `--router-ip <ROUTER_IP>` to the script.

It also defaults to admin username: `admin`. This can be changed by setting the
environment variable ROUTER_USERNAME when calling the script.

## Notes

This tool was developed against the router firmware version: 19.3B70-1.2.49.
This tool may not work on different versions (it is untested).

I have a small write up on the [reverse engineering notes here][0].

It is also important not to store the password in a trivial to access manner as
that could be a security risk. This script makes no attempt to handle the
security of the password, it simply expects to receive the password via an
environment variable and puts no requirements on how that environment gets set.

## License

The script is licensed under MIT. See LICENSE for details.

[0]: docs/reverse-engineering.md
[1]: https://pypi.org/project/pbkdf2/

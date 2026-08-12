from harvis.app import main
from harvis.lan_address import best_lan_ipv4
from harvis.remote_control import RemoteControlServer

# The mobile remote must advertise the physical LAN address that a phone can
# actually reach, rather than whichever adapter owns an Internet/VPN route.
RemoteControlServer._local_ipv4 = staticmethod(best_lan_ipv4)

if __name__ == "__main__":
    raise SystemExit(main())

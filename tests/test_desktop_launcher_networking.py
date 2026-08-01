import unittest

import desktop_launcher


class DesktopLauncherNetworkingTests(unittest.TestCase):
    def test_public_url_uses_lan_ip_when_binding_all_interfaces(self):
        url = desktop_launcher.public_app_url(8788, bind_host="0.0.0.0", lan_ip="192.168.1.23")
        self.assertEqual(url, "http://192.168.1.23:8788/?v=desktop-exe")

    def test_public_url_falls_back_to_localhost_when_no_lan_ip(self):
        url = desktop_launcher.public_app_url(8788, bind_host="0.0.0.0", lan_ip=None)
        self.assertEqual(url, "http://127.0.0.1:8788/?v=desktop-exe")

    def test_public_url_keeps_localhost_when_binding_loopback_only(self):
        url = desktop_launcher.public_app_url(8788, bind_host="127.0.0.1", lan_ip="192.168.1.23")
        self.assertEqual(url, "http://127.0.0.1:8788/?v=desktop-exe")


if __name__ == "__main__":
    unittest.main()

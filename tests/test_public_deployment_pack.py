from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicDeploymentPackTests(unittest.TestCase):
    def test_public_deployment_pack_contains_reverse_proxy_and_env_template(self):
        deploy_dir = ROOT / "deploy" / "public"
        required = [
            deploy_dir / "docker-compose.public.yml",
            deploy_dir / "Caddyfile",
            deploy_dir / ".env.public.example",
            ROOT / "PUBLIC_DEPLOYMENT.md",
        ]
        for path in required:
            self.assertTrue(path.exists(), f"{path} should exist")

        compose = (deploy_dir / "docker-compose.public.yml").read_text(encoding="utf-8")
        caddyfile = (deploy_dir / "Caddyfile").read_text(encoding="utf-8")
        env = (deploy_dir / ".env.public.example").read_text(encoding="utf-8")
        doc = (ROOT / "PUBLIC_DEPLOYMENT.md").read_text(encoding="utf-8")

        self.assertIn("caddy", compose)
        self.assertIn("COOKIE_SECURE: \"1\"", compose)
        self.assertIn("{$PUBLIC_DOMAIN}", caddyfile)
        self.assertIn("reverse_proxy app:8787", caddyfile)
        self.assertIn("LAOMA_ADMIN_PASSWORD=", env)
        self.assertIn("POSTGRES_PASSWORD=", env)
        self.assertIn("PUBLIC_DOMAIN=", env)
        self.assertIn("docker compose", doc)
        self.assertIn("HTTPS", doc)


if __name__ == "__main__":
    unittest.main()

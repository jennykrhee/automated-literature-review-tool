from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

checks = {
    'ANTHROPIC_API_KEY': bool(os.getenv('ANTHROPIC_API_KEY')),
    'OPENALEX_API_KEY': bool(os.getenv('OPENALEX_API_KEY')),
    'OBSIDIAN_VAULT_PATH': bool(os.getenv('OBSIDIAN_VAULT_PATH')),
}
for key, ok in checks.items():
    print(f"{'OK' if ok else 'MISSING'} {key}")

vault = Path(os.getenv('OBSIDIAN_VAULT_PATH', '')).expanduser()
if vault:
    print(f"Vault exists: {vault.exists()} -> {vault}")

profile = ROOT / 'config' / 'research_profile.yaml'
journals = ROOT / 'config' / 'journals.yaml'
prompt = ROOT / 'prompts' / 'relevance.md'
for path in [profile, journals, prompt]:
    print(f"{'OK' if path.exists() else 'MISSING'} {path}")

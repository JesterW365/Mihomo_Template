import argparse
import re
from pathlib import Path


COMPONENT_ORDER = ("head", "dns", "sniffer", "strategy", "rules")
RULE_SET_PATTERNS = (
    re.compile(r"\bRULE-SET\s*,\s*([A-Za-z0-9_-]+)"),
    re.compile(r"\brule-set:([A-Za-z0-9_-]+)"),
)


def strip_blank_and_comment_lines(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines) + ("\n" if lines else "")


def extract_provider_references(text):
    references = set()
    for pattern in RULE_SET_PATTERNS:
        references.update(pattern.findall(text))
    return references


def load_yaml_file(path):
    raise RuntimeError("load_yaml_file is not used by the text-based merger")


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_profile_file(path):
    if not path.is_file():
        raise FileNotFoundError(f"未找到文件: {path}")

    profile = {}
    components = {}
    in_components = False

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith((" ", "\t")):
            in_components = False
            key, separator, value = stripped.partition(":")
            if not separator:
                raise ValueError(f"profile 行格式错误: {path}: {line}")
            if key == "components":
                in_components = True
                profile["components"] = components
            else:
                profile[key] = unquote(value)
            continue

        if in_components:
            key, separator, value = stripped.partition(":")
            if not separator:
                raise ValueError(f"profile 组件行格式错误: {path}: {line}")
            components[key] = unquote(value)

    return profile


def load_profile(root, profile_name):
    profile_path = root / "profiles" / f"{profile_name}.yaml"
    profile = parse_profile_file(profile_path)
    components = profile.get("components")
    if not isinstance(components, dict):
        raise ValueError(f"profile 缺少 components 映射: {profile_path}")
    if "output" not in profile:
        raise ValueError(f"profile 缺少 output 字段: {profile_path}")
    return profile


def read_profile_components(root, profile):
    components = profile["components"]
    component_texts = {}
    for component_name in COMPONENT_ORDER:
        component_ref = components.get(component_name)
        if not component_ref:
            continue
        component_path = root / "components" / component_ref
        raw_text = component_path.read_text(encoding="utf-8-sig")
        component_texts[component_name] = strip_blank_and_comment_lines(raw_text)
    if "strategy" not in component_texts:
        raise ValueError("profile 必须包含 strategy 组件")
    if "rules" not in component_texts:
        raise ValueError("profile 必须包含 rules 组件")
    return component_texts


def load_provider_database(root):
    providers_path = root / "providers.yaml"
    if not providers_path.is_file():
        raise FileNotFoundError(f"未找到文件: {providers_path}")
    return parse_provider_database(providers_path.read_text(encoding="utf-8-sig"), providers_path)


def parse_provider_database(text, path):
    lines = text.splitlines()
    try:
        providers_index = next(index for index, line in enumerate(lines) if line.strip() == "rule-providers:")
    except StopIteration as error:
        raise ValueError(f"providers.yaml 缺少 rule-providers 映射: {path}") from error

    preamble = "\n".join(lines[:providers_index]).rstrip()
    blocks = {}
    current_name = None
    current_lines = []

    def flush_current():
        if current_name is not None:
            blocks[current_name] = "\n".join(current_lines).rstrip()

    provider_name_pattern = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
    for line in lines[providers_index + 1 :]:
        match = provider_name_pattern.match(line)
        if match:
            flush_current()
            current_name = match.group(1)
            current_lines = [line]
            continue
        if current_name is not None:
            current_lines.append(line)
    flush_current()

    if not blocks:
        raise ValueError(f"providers.yaml 中没有 provider 定义: {path}")
    return {"preamble": preamble, "blocks": blocks}


def select_referenced_providers(providers, references):
    blocks = providers["blocks"]
    missing = sorted(references - set(blocks))
    if missing:
        raise ValueError("providers.yaml 缺少以下规则源定义: " + ", ".join(missing))
    return {
        "preamble": providers["preamble"],
        "blocks": [blocks[name] for name in blocks if name in references],
    }


def dump_rule_providers(selected_providers):
    if not selected_providers["blocks"]:
        return ""
    chunks = []
    if selected_providers["preamble"]:
        chunks.append(selected_providers["preamble"])
    chunks.append("rule-providers:")
    chunks.extend(selected_providers["blocks"])
    return "\n".join(chunks) + "\n"


def build_output_text(component_texts, provider_text):
    chunks = []
    for component_name in ("head", "dns", "sniffer", "strategy"):
        text = component_texts.get(component_name)
        if text:
            chunks.append(text.rstrip())
    if provider_text:
        chunks.append(provider_text.rstrip())
    chunks.append(component_texts["rules"].rstrip())
    return "\n\n".join(chunks) + "\n"


def merge_profile(root, profile_name):
    root = Path(root)
    profile = load_profile(root, profile_name)
    component_texts = read_profile_components(root, profile)
    merged_component_text = "\n".join(component_texts.values())
    references = extract_provider_references(merged_component_text)
    providers = load_provider_database(root)
    selected_providers = select_referenced_providers(providers, references)
    output_text = build_output_text(component_texts, dump_rule_providers(selected_providers))

    output_path = root / "Custom_templates" / profile["output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Merge Mihomo template components by profile.")
    parser.add_argument("--profile", required=True, help="Profile name under profiles/, without .yaml")
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Project root. Defaults to the repository root.",
    )
    args = parser.parse_args()

    output_path = merge_profile(args.root, args.profile)
    print(f"生成完成: {output_path}")


if __name__ == "__main__":
    main()

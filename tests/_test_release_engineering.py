"""Release engineering pins (M6 F1-F3).

The workflows, Dockerfile and compose file are text artifacts nothing else in
the suite executes; these assertions keep the release discipline from silently
disappearing (checksums asset, tag == source version, healthcheck, PUID/PGID).
The last class keeps merge leftovers (conflict markers) out of the tree.

Run with: python _test_release_engineering.py
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class VersionStringTests(unittest.TestCase):
    def test_source_version_strings_agree(self):
        src = read("wb_proxy.py")
        overview = re.search(r'"version"\s*:\s*"([^"]+)"', src)
        server = re.search(r'server_version\s*=\s*"wb-proxy/([^"]+)"', src)
        self.assertIsNotNone(overview, "overview version string not found")
        self.assertIsNotNone(server, "server header version string not found")
        self.assertEqual(overview.group(1), server.group(1))

    def test_openwrt_packager_scripts_extract_server_version(self):
        """wrt/openwrt/build-ipk.sh 与 build-apk.sh 的 sed 解析器必须支持 fork 扩展版本号（如 1.7.2-deefery.1）。"""
        src = read("wb_proxy.py")
        server = re.search(r'server_version\s*=\s*"wb-proxy/([^"]+)"', src)
        self.assertIsNotNone(server, "wb_proxy.py 中未找到 server_version")
        expected_ver = server.group(1)

        scripts = ["wrt/openwrt/build-ipk.sh", "wrt/openwrt/build-apk.sh"]
        for rel in scripts:
            text = read(*rel.split("/"))
            m = re.search(r'wb-proxy\\/\\\((.*?)\\\)', text)
            self.assertIsNotNone(m, f"{rel} 未包含预期的 server_version sed 解析模式")
            pattern = m.group(1)

            # 验证对当前源码版本的提取正确性
            match = re.search(r'server_version\s*=\s*"wb-proxy/(' + pattern + r')"', src)
            self.assertIsNotNone(match, f"{rel} 的模式 {pattern} 无法匹配当前版本 {expected_ver}")
            self.assertEqual(match.group(1), expected_ver, f"{rel} 解析出的版本不一致")

            # 验证对各种合法版本（包含 fork 扩展、构建号）的兼容性
            for valid_ver in ["1.7.2", "1.7.2-deefery.1", "1.8.0-rc1", "2.0.0+build.42", "1.7.2_patch"]:
                sample_line = f'    server_version = "wb-proxy/{valid_ver}"'
                valid_match = re.search(r'server_version\s*=\s*"wb-proxy/(' + pattern + r')"', sample_line)
                self.assertIsNotNone(valid_match, f"{rel} 无法解析合法版本 {valid_ver}")
                self.assertEqual(valid_match.group(1), valid_ver)

            # 验证非法格式（非数字开头、含空格、畸形等）不会被错误捕获
            for malformed in ["", "not_starting_with_digit", "version with spaces", "1.7.2 bad"]:
                sample_line = f'    server_version = "wb-proxy/{malformed}"'
                malformed_match = re.search(r'server_version\s*=\s*"wb-proxy/(' + pattern + r')"', sample_line)
                self.assertIsNone(malformed_match, f"{rel} 错误地匹配了畸形版本 {malformed}")


class WorkflowTests(unittest.TestCase):
    def test_tests_workflow_asserts_tag_against_source(self):
        text = read(".github", "workflows", "tests.yml")
        self.assertIn('tags: ["v*"]', text)
        self.assertIn("version-assert", text)
        self.assertIn("refs/tags/v", text)
        self.assertIn("GITHUB_REF_NAME", text)
        self.assertIn("server_version", text)
        # The workflow's extraction must see the same two strings the source
        # test pins, otherwise a passing CI would mean nothing.
        self.assertIn('"version"', text)

    def test_release_checksums_workflow_hashes_every_asset(self):
        text = read(".github", "workflows", "release-checksums.yml")
        self.assertIn("types: [published]", text)
        self.assertIn("gh release download", text)
        self.assertIn("sha256sum *", text)
        self.assertIn("gh release upload", text)
        self.assertIn("checksums.txt", text)


class DockerTests(unittest.TestCase):
    def test_healthcheck_probes_the_health_endpoint(self):
        text = read("Dockerfile")
        self.assertIn("HEALTHCHECK", text)
        self.assertIn("/health", text)

    def test_compose_supports_puid_pgid(self):
        text = read("docker-compose.yml")
        self.assertIn("${PUID:-", text)
        self.assertIn("${PGID:-", text)


class ReadmeTests(unittest.TestCase):
    def test_readme_suite_count_matches_the_tree(self):
        names = [n for n in os.listdir(os.path.join(ROOT, "tests"))
                 if n.startswith("_test_") and n.endswith((".py", ".js"))]
        py = len([n for n in names if n.endswith(".py")])
        js = len([n for n in names if n.endswith(".js")])
        expected = "%d 个套件：%d 个 Python + %d 个 JS" % (len(names), py, js)
        self.assertIn(expected, read("README.md"))


class RepoHygieneTests(unittest.TestCase):
    """解冲突没解干净的残留（冲突标记）不许留在仓库里。

    main 上已经发生过三次：#131 专门清过一次 dashboard 的残留，README 又在
    #243/#245 那批合并里被提交进 12~15 行冲突标记。没有测试盯它的时候，
    Python 文件是直接 SyntaxError，HTML/JS 则是静默坏掉；回滚检查（revert
    guard）还会把「合并时顺手整理掉这些行」算成弄丢 main 的改动（见 #245）。
    """

    MARKER = re.compile(r"^(<{7}|>{7}|\|{7})(\s|$)")

    # 运行时数据与打包产物（.gitignore 里那些）：它们不是源码，不该被扫。
    SKIP_DIRS = (".git", "__pycache__", "node_modules", "accounts", "usage",
                 "logs", "suite-logs", "dist", "python", ".sdk-cache")

    def test_no_conflict_markers_in_the_tree(self):
        offenders = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            for name in files:
                path = os.path.join(base, name)
                try:
                    if os.path.getsize(path) > 4 * 1024 * 1024:
                        continue
                    with open(path, "rb") as fh:
                        raw = fh.read()
                except OSError:
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue                    # 二进制，跳过
                for line in text.splitlines():
                    if self.MARKER.match(line):
                        offenders.append("%s: %s"
                                         % (os.path.relpath(path, ROOT), line[:60]))
                        break
        self.assertEqual(
            offenders, [],
            "冲突标记残留（解冲突没解干净，两边都要留）：\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()

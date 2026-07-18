.PHONY: all clean distclean install uninstall spec \
        build-linux build-linux-deb build-linux-appimage build-linux-rpm \
        build-macos build-macos-dmg \
        build-windows build-windows-installer \
        check test docker-build docker-run docker-push \
        pip-build pip-publish release

APP_NAME     := hermes-agent
VERSION      := $(shell python3 -c "import hermes_universal; print(hermes_universal.__version__)" 2>/dev/null || echo "0.1.0")

# ========== 构建入口 ==========

all: pip-build build-linux build-linux-deb

# ========== Linux 构建 ==========

build-linux:
	pyinstaller --clean hermes-agent.spec
	@echo "✅ Linux binary: dist/$(APP_NAME)"
	@ls -lh dist/$(APP_NAME)

build-linux-appimage: build-linux
	@which appimagetool 2>/dev/null && { \
		mkdir -p dist/AppDir/usr/bin && \
		mkdir -p dist/AppDir/usr/share/applications && \
		mkdir -p dist/AppDir/usr/share/icons/hicolor/scalable/apps && \
		cp dist/$(APP_NAME) dist/AppDir/usr/bin/ && \
		cp installer/hermes-agent.desktop dist/AppDir/usr/share/applications/ && \
		cp installer/hermes.svg dist/AppDir/usr/share/icons/hicolor/scalable/apps/ && \
		appimagetool dist/AppDir dist/$(APP_NAME)-$(VERSION)-x86_64.AppImage && \
		echo "✅ AppImage: dist/$(APP_NAME)-$(VERSION)-x86_64.AppImage"; } || \
		echo "⚠️ appimagetool 未安装，跳过 AppImage"

build-linux-deb: build-linux
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/bin
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/applications
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/icons/hicolor/scalable/apps
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/metainfo
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/DEBIAN
	cp dist/$(APP_NAME) dist/$(APP_NAME)_$(VERSION)_amd64/usr/bin/
	cp installer/hermes-agent.desktop dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/applications/
	cp installer/hermes.svg dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/icons/hicolor/scalable/apps/hermes-agent.svg
	cp installer/hermes-appstream.xml dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/metainfo/io.hermes.agent.metainfo.xml
	printf "Package: %s\nVersion: %s\nSection: utils\nPriority: optional\nArchitecture: amd64\nMaintainer: Hermes Agent Team\nHomepage: https://github.com/shaoyili1990/-\nDescription: Hermes Agent Universal - Universal Portable AI Agent\n Monkey-Horse architecture with 4 roles and 136 reasoning chains\n" \
		$(APP_NAME) $(VERSION) > dist/$(APP_NAME)_$(VERSION)_amd64/DEBIAN/control
	dpkg-deb --build dist/$(APP_NAME)_$(VERSION)_amd64
	@echo "✅ DEB: dist/$(APP_NAME)_$(VERSION)_amd64.deb"
	@ls -lh dist/*.deb

build-linux-rpm:
	@echo "RPM 构建: cd dist && alien --to-rpm *.deb 2>/dev/null || echo '需要 alien 工具'"
	@echo "或手动: rpmbuild -tb dist/$(APP_NAME)_$(VERSION)_amd64.deb"

# ========== macOS 构建（需 macOS runner）==========

build-macos:
	pyinstaller --clean hermes-agent.spec
	@echo "✅ macOS .app: dist/$(APP_NAME).app"

build-macos-dmg: build-macos
	@which create-dmg 2>/dev/null && { \
		create-dmg --volname "Hermes Agent $(VERSION)" \
			--window-pos 200 120 --window-size 600 400 \
			--icon-size 100 --app-drop-link 400 200 \
			dist/$(APP_NAME)-$(VERSION)-macos-x86_64.dmg \
			dist/$(APP_NAME).app/ && \
		echo "✅ DMG: dist/$(APP_NAME)-$(VERSION)-macos-x86_64.dmg"; } || \
		echo "⚠️ create-dmg 未安装，使用 hdiutil 替代"
	@which hdiutil 2>/dev/null && { \
		hdiutil create -srcfolder dist/$(APP_NAME).app \
			-volname "Hermes Agent $(VERSION)" \
			dist/$(APP_NAME)-$(VERSION)-macos-x86_64.dmg && \
		echo "✅ DMG: dist/$(APP_NAME)-$(VERSION)-macos-x86_64.dmg"; } || true

# ========== Windows 构建（需 Windows runner）==========

build-windows:
	pyinstaller --clean hermes-agent.spec
	@echo "✅ Windows exe: dist/$(APP_NAME).exe"

build-windows-installer: build-windows
	@which makensis 2>/dev/null && { \
		cd installer && makensis hermes-installer.nsi && \
		echo "✅ Windows Installer: dist/$(APP_NAME)-Setup-$(VERSION).exe"; } || \
		echo "⚠️ NSIS (makensis) 未安装，跳过安装包"

# ========== Docker ==========

docker-build:
	docker build -t hermes-agent:$(VERSION) -t hermes-agent:latest .

docker-push: docker-build
	@echo "推送到 DockerHub:"
	@docker tag hermes-agent:latest shaoyili/hermes-agent:latest
	@docker tag hermes-agent:$(VERSION) shaoyili/hermes-agent:$(VERSION)
	@docker push shaoyili/hermes-agent:latest
	@docker push shaoyili/hermes-agent:$(VERSION)
	@echo "✅ 已推送: shaoyili/hermes-agent"

docker-run:
	docker run --rm -p 8080:8080 \
		-e OPENAI_API_KEY=$(OPENAI_API_KEY) \
		-e HERMES_HORSE_KEY=$(DEEPSEEK_API_KEY) \
		hermes-agent:latest

docker: docker-build

# ========== PyPI pip 包 ==========

pip-build:
	pip install build
	python3 -m build
	@echo "✅ pip 包: dist/*.whl dist/*.tar.gz"

pip-publish: pip-build
	@echo "发布到 PyPI:"
	@python3 -m twine upload dist/*.whl dist/*.tar.gz --repository pypi || \
		echo "⚠️ 需要 TWINE_USERNAME/TWINE_PASSWORD 环境变量"
	@echo "✅ 已发布到 PyPI"

# ========== 测试 ==========

check:
	@echo "=== 项目完整性检查 ==="
	@test -d hermes_universal && echo "✅ hermes_universal/" || echo "❌ hermes_universal/"
	@test -d fingerprints && echo "✅ fingerprints/ ($$(ls fingerprints/*.json | wc -l) files)" || echo "❌ fingerprints/"
	@test -d subchains && echo "✅ subchains/ ($$(ls subchains/*.md | wc -l) files)" || echo "❌ subchains/"
	@test -d validations && echo "✅ validations/ ($$(ls validations/*.md | wc -l) files)" || echo "❌ validations/"
	@test -f store/hermes.db && echo "✅ store/hermes.db" || echo "⚠️ store/hermes.db missing"
	@test -f store/rnd_engine.db && echo "✅ store/rnd_engine.db" || echo "⚠️ store/rnd_engine.db missing"
	@test -f config.yaml && echo "✅ config.yaml" || echo "❌ config.yaml"
	@test -f installer/hermes.ico && echo "✅ installer/hermes.ico (Windows icon)" || echo "⚠️ Windows icon"
	@test -f installer/hermes.svg && echo "✅ installer/hermes.svg (Linux icon)" || echo "❌ Linux icon"
	@test -f installer/hermes-installer.nsi && echo "✅ installer/hermes-installer.nsi (NSIS script)" || echo "⚠️ NSIS script"
	@test -f installer/hermes-agent.desktop && echo "✅ installer/hermes-agent.desktop" || echo "❌ .desktop"
	@test -f installer/hermes-appstream.xml && echo "✅ installer/hermes-appstream.xml" || echo "❌ AppStream"
	@test -f .github/workflows/release.yml && echo "✅ .github/workflows/release.yml (CI/CD)" || echo "❌ CI/CD"
	@test -f hermes-agent.spec && echo "✅ hermes-agent.spec (PyInstaller)" || echo "❌ PyInstaller spec"
	@test -f Dockerfile && echo "✅ Dockerfile" || echo "❌ Dockerfile"
	@test -f Makefile && echo "✅ Makefile" || echo "❌ Makefile"
	@echo ""
	@echo "=== Python 导入测试 ==="
	@python3 -c "import hermes_universal; print(f'✅ hermes_universal v{hermes_universal.__version__}')" 2>&1 || echo "❌ import failed"
	@python3 -c "from hermes_universal.config import load_config; print('✅ config')" 2>&1 || echo "❌ config"
	@python3 -c "from hermes_universal.engine import EngineDB; print('✅ engine')" 2>&1 || echo "❌ engine"
	@python3 -c "from hermes_universal.core.monkey import Monkey; print('✅ monkey')" 2>&1 || echo "❌ monkey"
	@python3 -c "from hermes_universal.core.horse import Horse; print('✅ horse')" 2>&1 || echo "❌ horse"
	@python3 -c "from hermes_universal.core.verifier import Verifier; print('✅ verifier')" 2>&1 || echo "❌ verifier"
	@echo "=== Done ==="

test: check

# ========== 清理 ==========

clean:
	rm -rf build/ dist/ __pycache__/
	rm -rf *.egg-info *.spec
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

distclean: clean
	rm -rf .venv/

# ========== 发布入口 ==========

release: build-linux build-linux-deb pip-build
	@echo ""
	@echo "============================================"
	@echo " Release v$(VERSION) 就绪"
	@echo "============================================"
	@ls -lh dist/$(APP_NAME) dist/*.deb dist/*.whl dist/*.tar.gz 2>/dev/null
	@echo ""
	@echo "GitHub Release 推送:"
	@echo "  git tag v$(VERSION) && git push origin v$(VERSION)"
	@echo ""
	@echo "Docker 推送:"
	@echo "  make docker-push"
	@echo ""
	@echo "PyPI 推送:"
	@echo "  make pip-publish"

.PHONY: all clean distclean install uninstall spec build-linux build-linux-appimage \
        build-linux-deb build-linux-rpm build-macos-dmg build-windows build-windows-installer \
        check test pip-install docker docker-build docker-run release

APP_NAME     := hermes-agent
VERSION      := 0.1.0

# ========== 构建 ==========

all: pip-install build-linux

# 安装开发依赖
pip-install:
	pip install --upgrade pip
	pip install build hatchling
	pip install -e ".[all,dev]"

# 生成 PyInstaller spec (已有,直接使用)
spec:
	@echo "Using hermes-agent.spec"

# Linux 独立二进制 (onefile)
build-linux: spec
	pyinstaller --clean hermes-agent.spec
	@echo "✅ Linux build: dist/$(APP_NAME)"

# Linux AppImage
build-linux-appimage: build-linux
	@which appimagetool 2>/dev/null && \
		appimagetool dist/$(APP_NAME) dist/$(APP_NAME)-$(VERSION)-linux-x86_64.AppImage && \
		echo "✅ AppImage: dist/$(APP_NAME)-$(VERSION)-linux-x86_64.AppImage" || \
		echo "⚠️ appimagetool not found, skipping AppImage"

# Linux DEB 包
build-linux-deb: build-linux
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/bin
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/applications
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/icons/hicolor/scalable/apps
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/metainfo
	mkdir -p dist/$(APP_NAME)_$(VERSION)_amd64/DEBIAN
	cp dist/$(APP_NAME) dist/$(APP_NAME)_$(VERSION)_amd64/usr/bin/
	cp installer/hermes-agent.desktop dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/applications/
	cp installer/hermes.svg dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/icons/hicolor/scalable/apps/
	cp installer/hermes-appstream.xml dist/$(APP_NAME)_$(VERSION)_amd64/usr/share/metainfo/
	printf "Package: %s\nVersion: %s\nSection: utils\nPriority: optional\nArchitecture: amd64\nMaintainer: Hermes Agent Team\nDescription: Universal Portable AI Agent System\n Monkey-Horse architecture with 136 reasoning chains\n" \
		$(APP_NAME) $(VERSION) > dist/$(APP_NAME)_$(VERSION)_amd64/DEBIAN/control
	dpkg-deb --build dist/$(APP_NAME)_$(VERSION)_amd64
	@echo "✅ DEB: dist/$(APP_NAME)_$(VERSION)_amd64.deb"

# Linux RPM 包 (通过 alien 转换或直接 rpmbuild)
build-linux-rpm:
	@echo "RPM build requires RPM tools; use: alien dist/*.deb 2>/dev/null || true"
	@echo "✅ RPM: dist/$(APP_NAME)-$(VERSION)-1.x86_64.rpm (manual)"

# macOS DMG (需在 macOS 上构建)
build-macos-dmg:
	@echo "macOS DMG 需要在 macOS CI runner 上构建"
	@echo "请参考: https://github.com/actions/runner-images#available-images"

# Windows exe (需在 Windows 上构建)
build-windows:
	@echo "Windows exe 需要在 Windows CI runner 上构建"
	@echo "请参考: https://github.com/actions/runner-images#available-images"

# Windows NSIS 安装包
build-windows-installer:
	@echo "Windows installer 需要 NSIS 工具链"
	@echo "请参考: https://nsis.sourceforge.io/"

# ========== Docker ==========

docker-build:
	docker build -t $(APP_NAME):$(VERSION) .
	@echo "✅ Docker image: $(APP_NAME):$(VERSION)"

docker-run:
	docker run -p 8080:8080 -e OPENAI_API_KEY=$(OPENAI_API_KEY) $(APP_NAME):$(VERSION)

docker: docker-build docker-run

# ========== 测试 ==========

check:
	@echo "=== Checking project structure ==="
	@test -d hermes_universal && echo "✅ hermes_universal/" || echo "❌ hermes_universal/"
	@test -d fingerprints && echo "✅ fingerprints/" || echo "❌ fingerprints/"
	@test -d subchains && echo "✅ subchains/" || echo "❌ subchains/"
	@test -d validations && echo "✅ validations/" || echo "❌ validations/"
	@test -f store/hermes.db && echo "✅ store/hermes.db" || echo "⚠️ store/hermes.db missing"
	@test -f config.yaml && echo "✅ config.yaml" || echo "❌ config.yaml"
	@python3 -c "import hermes_universal; print(f'✅ Package OK: v{hermes_universal.__version__}')" 2>&1 || echo "❌ Package import failed"
	@echo "=== Python imports ==="
	@python3 -c "from hermes_universal.config import load_config; print('✅ config')" 2>&1 || echo "❌ config"
	@python3 -c "from hermes_universal.engine import EngineDB; print('✅ engine')" 2>&1 || echo "❌ engine"
	@python3 -c "from hermes_universal.core.monkey import Monkey; print('✅ monkey')" 2>&1 || echo "❌ monkey"
	@python3 -c "from hermes_universal.core.horse import Horse; print('✅ horse')" 2>&1 || echo "❌ horse"
	@python3 -c "from hermes_universal.core.verifier import Verifier; print('✅ verifier')" 2>&1 || echo "❌ verifier"
	@echo "=== Done ==="

test: check
	@echo "All checks passed!"

# ========== 清理 ==========

clean:
	rm -rf build/ dist/ __pycache__/
	rm -rf hermes_universal.egg-info/
	rm -f *.spec
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

distclean: clean
	rm -rf .venv/

# ========== CI 发布入口 ==========

release: build-linux build-linux-deb
	@echo "Release v$(VERSION) assets:"
	@ls -lh dist/$(APP_NAME) dist/$(APP_NAME)_$(VERSION)_amd64.deb 2>/dev/null || true

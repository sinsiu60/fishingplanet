"""p4a 로컬 레시피: pygame 2.6.1 (기본 레시피 2.1.0은 Python 3.14에서 Cython 생성 C가 컴파일되지 않음).

p4a 기본 pygame 레시피와 같은 빌드 방식에, 버전만 올리고 미리 생성된 Cython C를 지워
호스트 파이썬에 설치한 최신 Cython(3.14 지원)으로 다시 만들게 한다. buildozer.spec 의 p4a.local_recipes 로 쓰인다.
"""
import glob
import os
from os.path import join

from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class Pygame2Recipe(CompiledComponentsPythonRecipe):
    version = '2.6.1'
    url = 'https://github.com/pygame/pygame/archive/{version}.tar.gz'

    site_packages_name = 'pygame'
    name = 'pygame'

    depends = ['sdl2', 'sdl2_image', 'sdl2_mixer', 'sdl2_ttf', 'setuptools', 'jpeg', 'png']
    hostpython_prerequisites = ['setuptools', 'cython>=3.1,<3.3']
    call_hostpython_via_targetpython = False  # Due to setuptools
    install_in_hostpython = False

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            # .pyx 에서 생성된 C 를 지우면 setup.py 가 Cython 으로 다시 만든다
            for pyx in glob.glob(join("src_c", "cython", "pygame", "**", "*.pyx"), recursive=True):
                rel = os.path.relpath(pyx, join("src_c", "cython", "pygame"))
                c = join("src_c", rel[:-4] + ".c")
                if os.path.exists(c):
                    os.remove(c)

            setup_template = open(join("buildconfig", "Setup.Android.SDL2.in")).read()
            # pygame 2.6.1 안드로이드 템플릿 버그: aarch64 에선 NEON(sse2neon)으로 SIMD 블리터를 켜는데
            # surface 모듈에 simd_blitters_sse2.c / _avx2.c 가 빠져 있어 폰에서 'cannot locate symbol
            # alphablit_alpha_sse2_argb_surf_alpha' 로 pygame.display 를 못 불러온다 (v0.8.0~0.8.4 시작 직후 종료).
            # 데스크톱 템플릿(Setup.SDL2.in)과 같게 두 파일을 넣는다 (avx2 쪽은 ARM 에선 빈 대체 함수로 컴파일됨).
            old = "surface src_c/surface.c"
            if "simd_blitters_sse2.c" not in setup_template:
                assert old in setup_template, "pygame Setup.Android.SDL2.in 의 surface 줄이 바뀜 — 레시피 확인"
                setup_template = setup_template.replace(
                    old, "surface src_c/simd_blitters_sse2.c src_c/simd_blitters_avx2.c src_c/surface.c")
            env = self.get_recipe_env(arch)
            env['ANDROID_ROOT'] = join(self.ctx.ndk.sysroot, 'usr')

            png = self.get_recipe('png', self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), '.libs')
            png_inc_dir = png.get_build_dir(arch)

            jpeg = self.get_recipe('jpeg', self.ctx)
            jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            sdl_mixer_includes = ""
            for include_dir in self.get_recipe('sdl2_mixer', self.ctx).get_include_dirs(arch):
                sdl_mixer_includes += f"-I{include_dir} "

            sdl2_image_includes = ""
            for include_dir in self.get_recipe('sdl2_image', self.ctx).get_include_dirs(arch):
                sdl2_image_includes += f"-I{include_dir} "

            setup_file = setup_template.format(
                sdl_includes=(
                    " -I" + join(self.ctx.bootstrap.build_dir, 'jni', 'SDL', 'include') +
                    " -L" + join(self.ctx.bootstrap.build_dir, "libs", str(arch)) +
                    " -L" + png_lib_dir + " -L" + jpeg_lib_dir + " -L" + arch.ndk_lib_dir_versioned),
                sdl_ttf_includes="-I" + join(self.ctx.bootstrap.build_dir, 'jni', 'SDL2_ttf'),
                sdl_image_includes=sdl2_image_includes,
                sdl_mixer_includes=sdl_mixer_includes,
                jpeg_includes="-I" + jpeg_inc_dir,
                png_includes="-I" + png_inc_dir,
                freetype_includes=""
            )
            open("Setup", "w").write(setup_file)

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['USE_SDL2'] = '1'
        env["PYGAME_CROSS_COMPILE"] = "TRUE"
        env["PYGAME_ANDROID"] = "TRUE"
        return env


recipe = Pygame2Recipe()

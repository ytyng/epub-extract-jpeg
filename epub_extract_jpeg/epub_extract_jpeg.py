#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EPUB ファイルを jpeg に展開する
"""
from __future__ import print_function, unicode_literals
import os
import sys
import subprocess
import shutil
import argparse
import tempfile
from xml.etree import ElementTree
import re


def procedure(file_path, convert_png=True):
    if not os.path.exists(file_path):
        print("{} is not exist.".format(file_path), file=sys.stderr)
        return

    output_dir, ext = os.path.splitext(file_path)

    if ext != '.epub':
        print("{} is not epub.".format(file_path), file=sys.stderr)
        return

    if os.path.exists(output_dir):
        print("{} is already exists.".format(output_dir), file=sys.stderr)
        return

    temp_dir = tempfile.mkdtemp(suffix='epub-extract-')

    subprocess.Popen(
        ('unzip', file_path, "-d", temp_dir),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

    os.mkdir(output_dir)

    content_xml_path = find_content_xml_path(temp_dir)

    image_paths = _get_image_paths(content_xml_path)

    root_dir = os.path.dirname(content_xml_path)

    for i, image_path in enumerate(image_paths, start=1):
        _move_jpeg_file(root_dir, image_path, output_dir, i,
                        convert_png=convert_png)

    shutil.rmtree(temp_dir)


def _get_image_paths(content_xml_path):
    etree = parse_xml_with_recover(content_xml_path)
    manifest = etree.find('.//{http://www.idpf.org/2007/opf}manifest')
    items = manifest.findall('.//{http://www.idpf.org/2007/opf}item')

    image_paths_prior = []
    image_paths = []
    for item in items:
        media_type = item.attrib.get('media-type', None)
        if not media_type:
            continue
        if media_type not in {'image/jpeg', 'image/png'}:
            continue
        if element_is_prior(item):
            # 表紙だった。(表紙が最後にある場合がある)
            image_paths_prior.append(item.attrib['href'])
        else:
            image_paths.append(item.attrib['href'])

    return image_paths_prior + image_paths


def element_is_prior(element):
    """
    表紙エレメントか?
    """
    properties = element.attrib.get('properties', None)
    if properties and properties.startswith('cover'):
        return True
    element_id = element.attrib.get('id', None)
    if element_id == "cover":
        return True
    return False


def _move_jpeg_file(source_dir, image_path, output_dir,
                    page_index, convert_png=True):
    source_image_path = os.path.join(source_dir, image_path)

    if image_path.endswith('.png'):
        if convert_png:
            # PNGを変換する場合
            _convert_png_to_jpeg(
                source_dir, image_path, output_dir, page_index)
            return
        destination_image_name = '{:03d}.png'.format(page_index)
    else:
        destination_image_name = '{:03d}.jpg'.format(page_index)
    destination_image_path = os.path.join(
        output_dir, destination_image_name)
    shutil.move(source_image_path, destination_image_path)
    print('{} -> {}'.format(image_path, destination_image_name))


def _convert_png_to_jpeg(source_dir, image_path, output_dir, page_index):
    """
    PNG を Jpeg に変換して移動
    """
    try:
        from PIL import Image
    except ImportError:
        print('PNG image found. Converting png to jpeg, require PIL.',
              file=sys.stderr)
        print('Try: "pip install PIL" or "pip install pillow"',
              file=sys.stderr)
        raise

    source_image_path = os.path.join(source_dir, image_path)
    destination_image_name = '{:03d}.jpg'.format(page_index)
    destination_image_path = os.path.join(
        output_dir, destination_image_name)
    im = Image.open(source_image_path)
    im = im.convert("RGB")
    im.save(destination_image_path, 'jpeg', quality=70)
    os.remove(source_image_path)
    print('{} -> {}'.format(image_path, destination_image_name))


def find_content_xml_path(temp_dir):
    # content.xml のファイルパスを返す META-INF/container.xml で固定
    container_xml_path = os.path.join(temp_dir, 'META-INF', 'container.xml')
    etree = parse_xml_with_recover(container_xml_path)
    # rootfile タグを探す
    rootfile_node = etree.find(
        ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
    content_opf_path = rootfile_node.attrib['full-path']

    content_xml_path = os.path.join(temp_dir, content_opf_path)
    if os.path.exists(content_xml_path):
        return content_xml_path
    else:
        print('content_xml_path not found: {}', content_xml_path)


def parse_xml_with_recover(xml_path):
    """
    xmlをパース
    & の使い方が悪いファイルがある場合、
    それをパースしようとするとエラーになるので、失敗したら文字列置換してリトライする。
    http://stackoverflow.com/questions/13046240/parseerror-not-well-formed
    -invalid-token-using-celementtree
    ここには、lxml の場合の対応方法があるが、python3 のxml ではやり方不明のため
    ( ElementTree.XMLParser のコンストラクタには recover 引数が無い)、
    自力で置換する
    """
    try:
        etree = ElementTree.parse(xml_path)
        return etree
    except ElementTree.ParseError as e:
        # ParseError の場合のみ、修復を試みる
        print('{}, {}'.format(e.__class__.__name__, e))

    xml_source = open(xml_path).read()
    # 修復!
    xml_source = xml_repair(xml_source)
    return ElementTree.fromstring(xml_source)


re_entity = re.compile(r'(>[^<]*)(&)([^<]*<)')
re_replace = re.compile(r'&(?!\w*?;)')


def xml_repair(xml_source):
    def _replace(matcher):
        return re_replace.sub('&amp;', matcher.group(0))

    return re_entity.sub(_replace, xml_source)


def main():
    parser = argparse.ArgumentParser(description='Extract Jpeg files in EPUB')
    parser.add_argument(
        'epub_files', metavar='EPUB-Files', type=str, nargs='+',
        help='Target Epub Files')
    parser.add_argument(
        '--no-png-convert', dest='no_png_convert', action='store_true',
        default=False,
        help='No png convert to jpeg')

    args = parser.parse_args()

    for epub_file in args.epub_files:
        procedure(epub_file, convert_png=not args.no_png_convert)


if __name__ == '__main__':
    main()

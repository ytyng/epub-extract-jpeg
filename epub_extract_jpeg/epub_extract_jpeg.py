#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EPUB ファイルを jpeg に展開する
"""
from __future__ import print_function, unicode_literals

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

try:
    from pip.utils import cached_property
except ImportError:
    try:
        from django.utils.functional import cached_property
    except ImportError:
        raise


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


def convert_to_jpeg(source_file_path, destination_file_path, jpeg_quality=70):
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

    im = Image.open(source_file_path)
    im = im.convert("RGB")
    im.save(destination_file_path, 'jpeg', quality=jpeg_quality)
    os.remove(source_file_path)
    print('{} -> {}'.format(source_file_path, destination_file_path))


re_entity = re.compile(r'(>[^<]*)(&)([^<]*<)')
re_replace = re.compile(r'&(?!\w*?;)')


def xml_repair(xml_source):
    """
    XMLのソースコードの & を &amp; に変換する
    :param self:
    :param xml_source:
    :return:
    """

    def _replace(matcher):
        return re_replace.sub('&amp;', matcher.group(0))

    return re_entity.sub(_replace, xml_source)


class ImagePage(object):
    """
    画像ページ のクラス
    """

    class ItemHrefNotFound(Exception):
        pass

    class InvalidImageLength(Exception):
        pass

    class ImagePathAttrNotFound(Exception):
        pass

    def __init__(self, item_element, itemref_element, epub_extract_jpeg):
        self.item_element = item_element
        self.itemref_element = itemref_element
        self.epub_extract_jpeg = epub_extract_jpeg

    @cached_property
    def page_xhtml_path(self):
        """
        ページのXMLのパス
        例: item/xhtml/001.xhtml
        :return:
        """
        item_href = self.item_element.attrib.get('href', None)
        if not item_href:
            raise self.ItemHrefNotFound(self.item_element)

        return os.path.join(
            self.epub_extract_jpeg.content_base_dir, item_href)

    # page_xml_path = os.path.join(self.content_base_dir, item_href)

    @cached_property
    def page_xhtml_etree(self):
        # ページを解析
        return parse_xml_with_recover(self.page_xhtml_path)

    @cached_property
    def image_element(self):

        if self.item_element.attrib.get('properties') == 'svg':
            # SVGラッピング 日本のコミックEPUBでよくある形式
            svg = self.page_xhtml_etree.find(
                './/{http://www.w3.org/2000/svg}svg')
            images = svg.findall('.//{http://www.w3.org/2000/svg}image')
            # 画像パスの属性は {http://www.w3.org/1999/xlink}href

        else:
            # ここ未テスト
            images = self.page_xhtml_etree.findall(
                './/{http://www.w3.org/1999/xhtml}img')
            # 画像パスの属性は src

        if len(images) != 1:
            raise self.InvalidImageLength('{}, {}'.format(
                self.item_element, len(images)))

        return images[0]

    @cached_property
    def image_path(self):
        """
        画像のフルパス
        :return:
        """
        attr_names = [
            '{http://www.w3.org/1999/xlink}href',
            'src',
            '{http://www.w3.org/1999/xlink}src',
        ]

        for attr_name in attr_names:
            val = self.image_element.attrib.get(attr_name)
            if val:
                return os.path.join(os.path.dirname(self.page_xhtml_path), val)

        raise self.ImagePathAttrNotFound(self.image_element.attrib)

    # その他プロパティが必要であれば
    # self.image_element.attrib.get('width', None)
    # self.image_element.attrib.get('height', None)
    # self.image_element.attrib.get('width', None)

    @cached_property
    def is_png(self):
        return self.image_path.endswith('.png')


class EpubExtractJpeg(object):
    class IdRefNotFound(Exception):
        pass

    class ItemNotFound(Exception):
        pass

    def __init__(self, file_path, convert_png=True):

        self.file_path = file_path
        self.convert_png = convert_png

    def extract(self):
        if not os.path.exists(self.file_path):
            print("{} is not exist.".format(self.file_path), file=sys.stderr)
            return

        output_dir, ext = os.path.splitext(self.file_path)

        if ext != '.epub':
            print("{} is not epub.".format(self.file_path), file=sys.stderr)
            return

        if os.path.exists(output_dir):
            print("{} is already exists.".format(output_dir), file=sys.stderr)
            return

        self.temp_dir = tempfile.mkdtemp(suffix='epub-extract-')

        subprocess.Popen(
            ('unzip', self.file_path, "-d", self.temp_dir),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

        os.mkdir(output_dir)

        # root_dir = os.path.dirname(self.content_xml_path)

        for i, image_page in enumerate(self.get_image_pages(), start=1):
            self._move_jpeg_file(image_page, output_dir, i,
                                 convert_png=self.convert_png)

        shutil.rmtree(self.temp_dir)

    @cached_property
    def content_xml_path(self):
        # content.xml (standard.opf) のファイルパスを返す META-INF/container.xml で固定
        container_xml_path = os.path.join(self.temp_dir, 'META-INF',
                                          'container.xml')
        etree = parse_xml_with_recover(container_xml_path)
        # rootfile タグを探す
        rootfile_node = etree.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        content_opf_path = rootfile_node.attrib['full-path']

        content_xml_path = os.path.join(self.temp_dir, content_opf_path)
        if os.path.exists(content_xml_path):
            return content_xml_path
        else:
            print('content_xml_path not found: {}', content_xml_path)

    @cached_property
    def content_xml_etree(self):
        return parse_xml_with_recover(self.content_xml_path)

    @cached_property
    def content_base_dir(self):
        # ファイルのパス基準となるディレクトリ
        return os.path.dirname(self.content_xml_path)

    @cached_property
    def items_dict(self):
        """
        id をキーにした item の辞書
        """
        manifest = self.content_xml_etree.find(
            './/{http://www.idpf.org/2007/opf}manifest')
        items = manifest.findall('.//{http://www.idpf.org/2007/opf}item')
        items_dict = {}
        for item in items:
            id = item.attrib.get('id')
            items_dict[id] = item
        return items_dict

    @cached_property
    def itemrefs(self):
        """
        spine > itemref をページ順に返すジェネレータ
        """
        spine = self.content_xml_etree.find(
            './/{http://www.idpf.org/2007/opf}spine')
        itemrefs = spine.findall('.//{http://www.idpf.org/2007/opf}itemref')
        for itemref in itemrefs:
            yield itemref

    def get_image_pages(self):
        items_dict = self.items_dict

        for itemref in self.itemrefs:

            idref = itemref.attrib.get('idref', None)
            if not idref:
                raise self.IdRefNotFound(itemref)

            if idref not in items_dict:
                raise self.ItemNotFound(idref)

            item = items_dict[idref]

            page_image = ImagePage(item, itemref, self)
            yield page_image

    def _move_jpeg_file(self, image_page, output_dir,
                        page_index, convert_png=True):
        source_image_path = image_page.image_path

        if image_page.is_png:
            if convert_png:
                # PNGを変換する場合
                destination_image_name = '{:03d}.jpg'.format(page_index)
                destination_image_path = os.path.join(
                    output_dir, destination_image_name)
                convert_to_jpeg(source_image_path, destination_image_path)
                return
            destination_image_name = '{:03d}.png'.format(page_index)
        else:
            destination_image_name = '{:03d}.jpg'.format(page_index)
        destination_image_path = os.path.join(
            output_dir, destination_image_name)
        shutil.move(source_image_path, destination_image_path)
        print('{} -> {}'.format(source_image_path, destination_image_name))


def procedure(file_path, convert_png=True):
    epub_extract_jpeg = EpubExtractJpeg(file_path, convert_png=convert_png)
    epub_extract_jpeg.extract()


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

~~~~~~~~~~~~~~~~~
epub-extract-jpeg
~~~~~~~~~~~~~~~~~

EPUBファイルを展開し、中の Jpeg ファイルを連番画像にします。


Install
-------

::

  $ pip install epub-extract-jpeg


Requirements
------------

unzip

PIL: 画像が PNG だった場合、Jpeg に変換を試みますがその時に使います。
この処理は、--no-convert-png オプションが与えられた場合行いません。


使い方
---

::

  $ epub-extract-jpeg xxxx.epub

xxx ディレクトリが作られ、その中に連番画像が作られます。


注意
--

EPUB XML を解析する際、本来であれば 各ページの xhtml ファイルを解析し、含まれている img タグを見なければいけないのですが、
処理を簡略化するために 各 xhtml の中身までは理解しません。

content.xml の中にリストされている画像を、すべて連番だと想定して処理を行います。

そのため、例えば content.xml と xhtml の対応を難読化している場合などは、ページの順番がおかしくなることが予想されます。
ただし、このような EPUB にはいまだに遭遇したことはありません。

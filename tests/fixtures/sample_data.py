"""测试用的示例数据"""

from kintone_scraper.models import Article, Section, Category

# 示例HTML内容
SAMPLE_HTML_WITH_IMAGES = '''
<article>
    <h1>kintone REST API 基础</h1>
    <p>这是一篇关于kintone REST API的文章。</p>
    <img src="https://cybozudev.kf5.com/hc/article_attachments/360000123456/api_flow.png" alt="API流程图">
    <p>更多内容...</p>
    <img src="/hc/article_attachments/360000789012/example_code.png" alt="示例代码">
    <div class="code-block">
        <pre><code>GET /k/v1/records.json</code></pre>
    </div>
</article>
'''

SAMPLE_HTML_NO_IMAGES = '''
<article>
    <h1>kintone JavaScript API 基础</h1>
    <p>这是一篇纯文本文章，没有图片。</p>
    <p>包含一些代码示例：</p>
    <pre><code>kintone.events.on('app.record.create.show', function(event) {
    console.log(event);
});</code></pre>
</article>
'''

SAMPLE_SECTION_HTML = '''
<html>
<body>
    <h1>kintone REST API</h1>
    <div class="article-list">
        <a href="/hc/kb/article/200733/">kintone REST API共通规格</a>
        <a href="/hc/kb/article/201594/">获取记录（GET）</a>
        <a href="/hc/kb/article/201603/">添加记录（POST）</a>
        <a href="/hc/kb/article/201605/">更新记录（PUT）</a>
        <a href="/hc/kb/article/201606/">删除记录（DELETE）</a>
    </div>
</body>
</html>
'''

# 示例数据模型
def create_sample_article() -> Article:
    """创建示例文章"""
    return Article(
        url="https://cybozudev.kf5.com/hc/kb/article/200733/",
        title="kintone REST API共通规格",
        content="这是关于kintone REST API共通规格的详细说明...",
        html_content=SAMPLE_HTML_WITH_IMAGES,
        category="kintone REST API",
        section_title="kintone REST API",
        last_updated="2024年03月04日 10:02:12"
    )

def create_sample_section() -> Section:
    """创建示例章节"""
    articles = [
        "https://cybozudev.kf5.com/hc/kb/article/200733/",
        "https://cybozudev.kf5.com/hc/kb/article/201594/",
        "https://cybozudev.kf5.com/hc/kb/article/201603/",
        "https://cybozudev.kf5.com/hc/kb/article/201605/",
        "https://cybozudev.kf5.com/hc/kb/article/201606/"
    ]
    
    return Section(
        url="https://cybozudev.kf5.com/hc/kb/section/106250/",
        title="kintone REST API",
        description="kintone REST API相关文档",
        article_count=len(articles),
        articles=articles,
        category_path="API文档/kintone REST API"
    )

def create_sample_category() -> Category:
    """创建示例分类"""
    category = Category(
        name="API文档",
        path="API文档"
    )
    
    # 添加示例章节
    rest_api_section = create_sample_section()
    category.add_section(rest_api_section)
    
    js_api_section = Section(
        url="https://cybozudev.kf5.com/hc/kb/section/106251/",
        title="kintone JavaScript API",
        article_count=15,
        category_path="API文档/kintone JavaScript API"
    )
    category.add_section(js_api_section)
    
    return category

# 测试用的URL列表
SAMPLE_URLS = {
    'base_url': 'https://cybozudev.kf5.com/hc/',
    'sections': [
        'https://cybozudev.kf5.com/hc/kb/section/106250/',  # kintone REST API
        'https://cybozudev.kf5.com/hc/kb/section/106251/',  # kintone JavaScript API
        'https://cybozudev.kf5.com/hc/kb/section/106249/',  # kintone API指南
    ],
    'articles': [
        'https://cybozudev.kf5.com/hc/kb/article/200733/',  # REST API共通规格
        'https://cybozudev.kf5.com/hc/kb/article/201594/',  # 获取记录（GET）
        'https://cybozudev.kf5.com/hc/kb/article/201603/',  # 添加记录（POST）
    ],
    'images': [
        'https://cybozudev.kf5.com/hc/article_attachments/360000123456/api_flow.png',
        'https://cybozudev.kf5.com/hc/article_attachments/360000789012/example_code.png',
    ]
}

# 期望的分类结构
EXPECTED_CATEGORIES = {
    'API文档': [
        'kintone REST API',
        'kintone JavaScript API', 
        'kintone API指南',
        'cybozu User API/OAuth'
    ],
    '工具': [
        'SDK',
        '开发工具',
        '资源库'
    ],
    '新手教程': [
        '新手入门',
        'kintone API入门系列',
        'kintone自定义技巧'
    ],
    '插件': [
        '插件API/CSS',
        '插件开发',
        '插件范例'
    ]
}

# 模拟的HTTP响应
MOCK_RESPONSES = {
    'main_page': '''
    <html>
    <body>
        <div class="category">
            <h2>kintone REST API</h2>
            <a class="more" href="/hc/kb/section/106250/">查看全部文档</a>
        </div>
        <div class="category">
            <h2>kintone JavaScript API</h2>
            <a class="more" href="/hc/kb/section/106251/">查看全部文档</a>
        </div>
    </body>
    </html>
    ''',
    
    'section_page': SAMPLE_SECTION_HTML,
    
    'article_page': f'''
    <html>
    <body>
        {SAMPLE_HTML_WITH_IMAGES}
        <div class="breadcrumb">
            <a href="#">首页</a>
            <a href="#">API文档</a>
            <a href="#">kintone REST API</a>
        </div>
        <time datetime="2024-03-04T10:02:12">2024年03月04日 10:02:12</time>
    </body>
    </html>
    '''
}


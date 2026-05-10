"""parts glossary table with multilingual terms

Revision ID: 0007_parts_glossary
Revises: 0006_bike_catalog_image
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_parts_glossary"
down_revision = "0006_bike_catalog_image"
branch_labels = None
depends_on = None
SCHEMA = "watcher"


def upgrade() -> None:
    op.create_table(
        "parts_glossary",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("term_en", sa.String(length=200), nullable=False),
        sa.Column("term_zh", sa.String(length=200), nullable=True),
        sa.Column("term_ja", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=60), nullable=False, server_default="general"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="seed"),
        sa.Column("contributed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_glossary_slug"),
        sa.UniqueConstraint("term_en", name="uq_glossary_term_en"),
        schema=SCHEMA,
    )
    op.execute(sa.text(
        f"CREATE INDEX glossary_term_en_trgm ON {SCHEMA}.parts_glossary USING GIN (term_en gin_trgm_ops)"
    ))
    op.execute(sa.text(
        f"CREATE INDEX glossary_term_zh_trgm ON {SCHEMA}.parts_glossary USING GIN (term_zh gin_trgm_ops)"
    ))
    op.execute(sa.text(
        f"CREATE INDEX glossary_term_ja_trgm ON {SCHEMA}.parts_glossary USING GIN (term_ja gin_trgm_ops)"
    ))
    op.create_index("glossary_category", "parts_glossary", ["category", "slug"], schema=SCHEMA)

    # Seed data: ~130 motorcycle parts in EN / zh-TW / JA
    op.execute(sa.text(f"""
        INSERT INTO {SCHEMA}.parts_glossary (slug, term_en, term_zh, term_ja, category, source) VALUES
        -- engine
        ('spark-plug',       'spark plug',       '火星塞',       'スパークプラグ',               'engine',     'seed'),
        ('piston',           'piston',            '活塞',         'ピストン',                     'engine',     'seed'),
        ('piston-ring',      'piston ring',       '活塞環',       'ピストンリング',               'engine',     'seed'),
        ('cylinder',         'cylinder',          '汽缸',         'シリンダー',                   'engine',     'seed'),
        ('cylinder-head',    'cylinder head',     '汽缸頭',       'シリンダーヘッド',             'engine',     'seed'),
        ('crankshaft',       'crankshaft',        '曲軸',         'クランクシャフト',             'engine',     'seed'),
        ('camshaft',         'camshaft',          '凸輪軸',       'カムシャフト',                 'engine',     'seed'),
        ('valve',            'valve',             '汽門',         'バルブ',                       'engine',     'seed'),
        ('valve-spring',     'valve spring',      '汽門彈簧',     'バルブスプリング',             'engine',     'seed'),
        ('rocker-arm',       'rocker arm',        '搖臂',         'ロッカーアーム',               'engine',     'seed'),
        ('connecting-rod',   'connecting rod',    '連桿',         'コンロッド',                   'engine',     'seed'),
        ('timing-chain',     'timing chain',      '正時鏈條',     'タイミングチェーン',           'engine',     'seed'),
        ('head-gasket',      'head gasket',       '汽缸頭墊片',   'ヘッドガスケット',             'engine',     'seed'),
        ('gasket',           'gasket',            '墊片',         'ガスケット',                   'engine',     'seed'),
        ('oil-pump',         'oil pump',          '機油泵',       'オイルポンプ',                 'engine',     'seed'),
        ('oil-filter',       'oil filter',        '機油濾芯',     'オイルフィルター',             'engine',     'seed'),
        ('air-filter',       'air filter',        '空氣濾芯',     'エアフィルター',               'engine',     'seed'),
        ('engine',           'engine',            '引擎',         'エンジン',                     'engine',     'seed'),
        ('crankcase',        'crankcase',         '曲軸箱',       'クランクケース',               'engine',     'seed'),
        ('bearing',          'bearing',           '軸承',         'ベアリング',                   'engine',     'seed'),
        ('engine-mount',     'engine mount',      '引擎支架',     'エンジンマウント',             'engine',     'seed'),
        -- brakes
        ('brake',            'brake',             '煞車',         'ブレーキ',                     'brakes',     'seed'),
        ('brake-pad',        'brake pad',         '煞車片',       'ブレーキパッド',               'brakes',     'seed'),
        ('brake-disc',       'brake disc',        '煞車盤',       'ブレーキディスク',             'brakes',     'seed'),
        ('brake-rotor',      'brake rotor',       '煞車碟盤',     'ブレーキローター',             'brakes',     'seed'),
        ('brake-caliper',    'brake caliper',     '煞車卡鉗',     'ブレーキキャリパー',           'brakes',     'seed'),
        ('brake-master-cylinder','brake master cylinder','煞車主缸','ブレーキマスターシリンダー','brakes',   'seed'),
        ('brake-lever',      'brake lever',       '煞車拉桿',     'ブレーキレバー',               'brakes',     'seed'),
        ('brake-hose',       'brake hose',        '煞車油管',     'ブレーキホース',               'brakes',     'seed'),
        ('brake-fluid',      'brake fluid',       '煞車油',       'ブレーキフルード',             'brakes',     'seed'),
        ('abs-sensor',       'ABS sensor',        'ABS感應器',    'ABSセンサー',                  'brakes',     'seed'),
        ('drum-brake',       'drum brake',        '鼓式煞車',     'ドラムブレーキ',               'brakes',     'seed'),
        ('brake-shoe',       'brake shoe',        '煞車蹄片',     'ブレーキシュー',               'brakes',     'seed'),
        -- electrical
        ('battery',          'battery',           '電池',         'バッテリー',                   'electrical', 'seed'),
        ('headlight',        'headlight',         '大燈',         'ヘッドライト',                 'electrical', 'seed'),
        ('tail-light',       'tail light',        '尾燈',         'テールランプ',                 'electrical', 'seed'),
        ('turn-signal',      'turn signal',       '方向燈',       'ウインカー',                   'electrical', 'seed'),
        ('horn',             'horn',              '喇叭',         'ホーン',                       'electrical', 'seed'),
        ('stator',           'stator',            '定子',         'ステーター',                   'electrical', 'seed'),
        ('rectifier',        'rectifier',         '整流器',       'レクチファイヤ',               'electrical', 'seed'),
        ('regulator-rectifier','regulator rectifier','穩壓整流器','レギュレーターレクチファイヤ','electrical','seed'),
        ('cdi-unit',         'CDI unit',          'CDI點火器',    'CDIユニット',                  'electrical', 'seed'),
        ('starter-motor',    'starter motor',     '起動馬達',     'スターターモーター',           'electrical', 'seed'),
        ('ignition-coil',    'ignition coil',     '點火線圈',     'イグニッションコイル',         'electrical', 'seed'),
        ('wiring-harness',   'wiring harness',    '線組',         'ワイヤーハーネス',             'electrical', 'seed'),
        ('instrument-cluster','instrument cluster','儀錶板',      'メーターパネル',               'electrical', 'seed'),
        ('speedometer',      'speedometer',       '速度表',       'スピードメーター',             'electrical', 'seed'),
        ('tachometer',       'tachometer',        '轉速表',       'タコメーター',                 'electrical', 'seed'),
        -- suspension
        ('fork',             'fork',              '前叉',         'フォーク',                     'suspension', 'seed'),
        ('shock',            'shock',             '避震器',       'ショック',                     'suspension', 'seed'),
        ('suspension',       'suspension',        '避震器',       'サスペンション',               'suspension', 'seed'),
        ('fork-seal',        'fork seal',         '前叉油封',     'フォークシール',               'suspension', 'seed'),
        ('fork-spring',      'fork spring',       '前叉彈簧',     'フォークスプリング',           'suspension', 'seed'),
        ('shock-absorber',   'shock absorber',    '後避震器',     'ショックアブソーバー',         'suspension', 'seed'),
        ('swing-arm',        'swing arm',         '後搖臂',       'スイングアーム',               'suspension', 'seed'),
        ('linkage',          'linkage',           '連桿組',       'リンケージ',                   'suspension', 'seed'),
        ('steering-stem',    'steering stem',     '方向管',       'ステアリングステム',           'suspension', 'seed'),
        ('triple-tree',      'triple tree',       '三角台',       'トリプルツリー',               'suspension', 'seed'),
        ('steering-damper',  'steering damper',   '方向穩定器',   'ステアリングダンパー',         'suspension', 'seed'),
        -- drivetrain
        ('chain',            'chain',             '鏈條',         'チェーン',                     'drivetrain', 'seed'),
        ('sprocket',         'sprocket',          '齒盤',         'スプロケット',                 'drivetrain', 'seed'),
        ('clutch',           'clutch',            '離合器',       'クラッチ',                     'drivetrain', 'seed'),
        ('clutch-plate',     'clutch plate',      '離合器片',     'クラッチプレート',             'drivetrain', 'seed'),
        ('clutch-spring',    'clutch spring',     '離合器彈簧',   'クラッチスプリング',           'drivetrain', 'seed'),
        ('front-sprocket',   'front sprocket',    '前齒盤',       'フロントスプロケット',         'drivetrain', 'seed'),
        ('rear-sprocket',    'rear sprocket',     '後齒盤',       'リアスプロケット',             'drivetrain', 'seed'),
        ('drive-belt',       'drive belt',        '傳動皮帶',     'ドライブベルト',               'drivetrain', 'seed'),
        ('transmission',     'transmission',      '變速箱',       'トランスミッション',           'drivetrain', 'seed'),
        ('clutch-cable',     'clutch cable',      '離合器鋼索',   'クラッチケーブル',             'drivetrain', 'seed'),
        -- exhaust
        ('exhaust',          'exhaust',           '排氣管',       'マフラー',                     'exhaust',    'seed'),
        ('muffler',          'muffler',           '消音器',       'サイレンサー',                 'exhaust',    'seed'),
        ('exhaust-header',   'exhaust header',    '排氣頭段',     'エキゾーストヘッダー',         'exhaust',    'seed'),
        ('exhaust-gasket',   'exhaust gasket',    '排氣墊片',     'エキゾーストガスケット',       'exhaust',    'seed'),
        ('exhaust-clamp',    'exhaust clamp',     '排氣管夾',     'エキゾーストクランプ',         'exhaust',    'seed'),
        ('catalytic-converter','catalytic converter','觸媒轉化器','触媒コンバーター',             'exhaust',    'seed'),
        ('heat-shield',      'heat shield',       '隔熱板',       'ヒートシールド',               'exhaust',    'seed'),
        -- fuel
        ('carburetor',       'carburetor',        '化油器',       'キャブレター',                 'fuel',       'seed'),
        ('fuel-tank',        'fuel tank',         '油箱',         '燃料タンク',                   'fuel',       'seed'),
        ('tank',             'tank',              '油箱',         'タンク',                       'fuel',       'seed'),
        ('fuel-injector',    'fuel injector',     '噴油嘴',       'インジェクター',               'fuel',       'seed'),
        ('throttle-body',    'throttle body',     '節氣門',       'スロットルボディ',             'fuel',       'seed'),
        ('fuel-pump',        'fuel pump',         '燃油泵',       'フューエルポンプ',             'fuel',       'seed'),
        ('fuel-filter',      'fuel filter',       '燃油濾清器',   'フューエルフィルター',         'fuel',       'seed'),
        ('fuel-cap',         'fuel cap',          '油箱蓋',       '燃料キャップ',                 'fuel',       'seed'),
        ('petcock',          'petcock',           '燃油旋塞',     'ペットコック',                 'fuel',       'seed'),
        ('throttle-cable',   'throttle cable',    '油門鋼索',     'スロットルケーブル',           'fuel',       'seed'),
        -- cooling
        ('radiator',         'radiator',          '水箱',         'ラジエーター',                 'cooling',    'seed'),
        ('thermostat',       'thermostat',        '恆溫器',       'サーモスタット',               'cooling',    'seed'),
        ('water-pump',       'water pump',        '水泵',         'ウォーターポンプ',             'cooling',    'seed'),
        ('coolant',          'coolant',           '冷卻液',       'クーラント',                   'cooling',    'seed'),
        ('radiator-hose',    'radiator hose',     '水管',         'ラジエーターホース',           'cooling',    'seed'),
        ('coolant-reservoir','coolant reservoir', '副水箱',       'リザーバータンク',             'cooling',    'seed'),
        ('radiator-fan',     'radiator fan',      '水箱風扇',     'ラジエーターファン',           'cooling',    'seed'),
        ('temperature-sensor','temperature sensor','水溫感應器',  '水温センサー',                 'cooling',    'seed'),
        ('oil-cooler',       'oil cooler',        '機油冷卻器',   'オイルクーラー',               'cooling',    'seed'),
        -- frame
        ('frame',            'frame',             '車架',         'フレーム',                     'frame',      'seed'),
        ('subframe',         'subframe',          '副車架',       'サブフレーム',                 'frame',      'seed'),
        ('footpeg',          'footpeg',           '腳踏',         'フットペグ',                   'frame',      'seed'),
        ('handlebar',        'handlebar',         '把手',         'ハンドル',                     'frame',      'seed'),
        ('grip',             'grip',              '握把',         'グリップ',                     'frame',      'seed'),
        ('mirror',           'mirror',            '後視鏡',       'ミラー',                       'frame',      'seed'),
        ('side-stand',       'side stand',        '側撐架',       'サイドスタンド',               'frame',      'seed'),
        ('center-stand',     'center stand',      '中撐架',       'センタースタンド',             'frame',      'seed'),
        ('crash-bar',        'crash bar',         '保桿',         'クラッシュバー',               'frame',      'seed'),
        ('cable',            'cable',             '拉線',         'ケーブル',                     'frame',      'seed'),
        -- body
        ('fairing',          'fairing',           '整流罩',       'カウル',                       'body',       'seed'),
        ('seat',             'seat',              '座墊',         'シート',                       'body',       'seed'),
        ('windscreen',       'windscreen',        '風鏡',         'スクリーン',                   'body',       'seed'),
        ('fender',           'fender',            '擋泥板',       'フェンダー',                   'body',       'seed'),
        ('seat-cowl',        'seat cowl',         '後座尾蓋',     'シートカウル',                 'body',       'seed'),
        ('tank-cover',       'tank cover',        '油箱蓋板',     'タンクカバー',                 'body',       'seed'),
        ('belly-pan',        'belly pan',         '下整流罩',     'ベリーパン',                   'body',       'seed'),
        -- wheels
        ('wheel',            'wheel',             '輪框',         'ホイール',                     'wheels',     'seed'),
        ('tire',             'tire',              '輪胎',         'タイヤ',                       'wheels',     'seed'),
        ('rim',              'rim',               '鋼圈',         'リム',                         'wheels',     'seed'),
        ('spoke',            'spoke',             '輻條',         'スポーク',                     'wheels',     'seed'),
        ('inner-tube',       'inner tube',        '內胎',         'チューブ',                     'wheels',     'seed'),
        ('wheel-bearing',    'wheel bearing',     '輪轂軸承',     'ホイールベアリング',           'wheels',     'seed'),
        ('axle',             'axle',              '車軸',         'アクスル',                     'wheels',     'seed'),
        ('valve-stem',       'valve stem',        '氣嘴',         'バルブステム',                 'wheels',     'seed'),
        -- fasteners
        ('bolt',             'bolt',              '螺絲',         'ボルト',                       'fasteners',  'seed'),
        ('clamp',            'clamp',             '夾具',         'クランプ',                     'fasteners',  'seed'),
        ('nut',              'nut',               '螺帽',         'ナット',                       'fasteners',  'seed'),
        ('washer',           'washer',            '墊圈',         'ワッシャー',                   'fasteners',  'seed'),
        ('rivet',            'rivet',             '鉚釘',         'リベット',                     'fasteners',  'seed'),
        ('clip',             'clip',              '扣夾',         'クリップ',                     'fasteners',  'seed'),
        ('o-ring',           'o-ring',            'O形環',        'Oリング',                      'fasteners',  'seed'),
        ('oil-seal',         'oil seal',          '油封',         'オイルシール',                 'fasteners',  'seed'),
        ('valve-seal',       'valve seal',        '汽門油封',     'バルブシール',                 'fasteners',  'seed'),
        -- general
        ('lever',            'lever',             '拉桿',         'レバー',                       'general',    'seed')
        ON CONFLICT (slug) DO NOTHING
    """))


def downgrade() -> None:
    op.drop_index("glossary_category", table_name="parts_glossary", schema=SCHEMA)
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.glossary_term_ja_trgm"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.glossary_term_zh_trgm"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {SCHEMA}.glossary_term_en_trgm"))
    op.drop_table("parts_glossary", schema=SCHEMA)

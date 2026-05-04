from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryHit:
    category: str
    subcategory: str | None = None


# Keyword → (top-level category, optional subcategory). First match wins.
# Slugs match watcher.categories.slug (populated by services/catalog_sync.py).
#
# Each tuple mixes English, Japanese (ja), and Traditional Chinese (zh-TW)
# keywords so JP-source listings (buyee, yahoo_auctions, monotaro) and TW
# webike listings get classified alongside the eBay ones. Substring match,
# so katakana like ブレーキパッド is matched as a single token; bare
# ブレーキ is intentionally avoided in the brakes rule because
# "ブレーキフルード" is a maintenance-oils listing, not a brake part.
_RULES: tuple[tuple[tuple[str, ...], CategoryHit], ...] = (
    # Modification subcategories
    (("muffler", "exhaust", "header", "mid pipe", "slip-on", "slip on",
      "マフラー", "サイレンサー", "エキゾースト", "エキパイ", "フルエキ", "スリップオン",
      "排氣管", "消音器"),
     CategoryHit("modification", "modification-exhaust")),
    (("piston", "crank", "cylinder", "camshaft", "engine head", "valve", "gasket",
      "carburetor", "carburettor", "oil cooler", "cam cover",
      "ピストン", "シリンダー", "カムシャフト", "カムカバー", "クランク", "ガスケット",
      "キャブレター", "キャブ", "オイルクーラー",
      "活塞", "汽缸", "凸輪軸", "墊片", "曲軸", "化油器"),
     CategoryHit("modification", "modification-engine")),
    (("caliper", "brake disc", "brake rotor", "rotor", "master cylinder", "brake line", "brake pad",
      "ブレーキパッド", "ブレーキディスク", "ブレーキローター", "ブレーキキャリパー",
      "キャリパー", "マスターシリンダー", "ブレーキホース",
      "煞車片", "煞車皮", "煞車盤", "煞車卡鉗"),
     CategoryHit("modification", "modification-brakes")),
    (("fork", "shock", "suspension", "swingarm", "steering damper", "triple tree", "stem",
      "フォーク", "ショック", "サスペンション", "スイングアーム", "ステアリングダンパー",
      "前叉", "避震器", "後搖臂"),
     CategoryHit("modification", "modification-steering")),
    (("ecu", "cdi", "stator", "rectifier", "coil", "harness", "starter motor", "ignition",
      "ハーネス", "レギュレーター", "レクチファイア", "ステーター", "スターター",
      "イグニッション", "メインハーネス",
      "線組", "整流器", "啟動馬達", "點火"),
     CategoryHit("modification", "modification-electrical")),
    (("frame", "subframe", "chassis", "engine mount", "rearset",
      "フレーム", "サブフレーム", "バックステップ", "エンジンマウント",
      "車架", "副車架", "後移腳踏"),
     CategoryHit("modification", "modification-chassis")),
    (("sprocket", "chain", "transmission", "clutch lever", "clutch kit", "shifter",
      "スプロケット", "チェーン", "クラッチ", "トランスミッション", "シフター",
      "齒盤", "鏈條", "離合器", "變速箱"),
     CategoryHit("modification", "modification-transmission")),
    (("fairing", "cowl", "seat cowl", "tank cover", "windshield", "fender", "tail section", "tank pad",
      "カウル", "シートカウル", "テールカウル", "タンクカバー", "フェンダー", "スクリーン",
      "タンク", "燃料タンク", "フューエルタンク",
      "整流罩", "風鏡", "擋泥板", "前土除", "油箱"),
     CategoryHit("modification", "modification-body")),

    # Maintenance
    (("oil filter", "engine oil", "fork oil", "brake fluid",
      "オイルフィルター", "エンジンオイル", "フォークオイル", "ブレーキフルード", "ブレーキオイル",
      "機油濾芯", "引擎機油", "煞車油"),
     CategoryHit("maintenance", "maintenance-oils")),
    (("tire", "tyre", "タイヤ", "輪胎"),
     CategoryHit("maintenance", "maintenance-tires")),
    (("battery", "バッテリー", "電池"),
     CategoryHit("maintenance", "maintenance-batteries")),
    (("air filter", "spark plug", "service kit",
      "エアフィルター", "エアクリーナー", "スパークプラグ", "プラグ",
      "空氣濾芯", "火星塞"),
     CategoryHit("maintenance", "maintenance-repair")),

    # Gear
    (("helmet", "ヘルメット", "安全帽"),
     CategoryHit("gear", "gear-helmets")),
    (("jacket", "glove", "riding suit", "leathers",
      "ジャケット", "グローブ", "ライディングスーツ",
      "騎士服", "手套"),
     CategoryHit("gear", "gear-apparel")),
    (("boot", "boots", "ブーツ", "車靴"),
     CategoryHit("gear", "gear-boots")),

    # Tools
    (("torque wrench", "socket set", "allen key",
      "トルクレンチ", "ソケットセット",
      "扭力扳手"),
     CategoryHit("tools", "tools-hand")),
    (("impact driver", "drill",
      "インパクトドライバー", "ドリル"),
     CategoryHit("tools", "tools-power")),
    (("oem", "genuine part", "original equipment",
      "純正", "純正部品", "原廠"),
     CategoryHit("oem", None)),
)


def classify(title: str, description: str | None = None) -> CategoryHit:
    # English keywords are lowercased; JP/CN script has no case so it passes through.
    text = " ".join([title or "", description or ""]).lower()
    for keywords, hit in _RULES:
        if any(kw in text for kw in keywords):
            return hit
    return CategoryHit("unknown", None)


def categorize_listing(title: str, description: str | None) -> str:
    """Backwards-compatible helper: returns top-level category slug only."""
    return classify(title, description).category

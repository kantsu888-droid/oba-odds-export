from datetime import datetime, timezone, timedelta

from pathlib import Path

from urllib.parse import urlencode

from urllib.request import Request, urlopen

from html import unescape

import csv

import re

import time

JST = timezone(timedelta(hours=9))

SCHEDULE_CACHE_MINUTES = 30

# 今回監視する競馬場

TRACKS = {

    "urawa": "18",

    "funabashi": "19",

    "oi": "20",

    "kawasaki": "21",

    "kochi": "31",

    "saga": "32",

}
EXTRA_RACES = {

    "2026-09-23": [

        ("sonoda", "27", 11),

        ("kasamatsu", "23", 11),

        ("monbetsu", "36", 12),

    ]

}
BASE_URL = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/DebaTable"

def get_start_time(track_code, race_date, race_no):

    params = {

        "k_raceDate": race_date.strftime("%Y/%m/%d"),

        "k_raceNo": race_no,

        "k_babaCode": track_code,

    }

    url = BASE_URL + "?" + urlencode(params)

    request = Request(

        url,

        headers={

            "User-Agent": "Mozilla/5.0"

        }

    )

    try:

        with urlopen(request, timeout=20) as response:

            html = response.read().decode("utf-8", errors="ignore")

    except Exception as e:

        print(f"取得失敗 code={track_code} race={race_no}: {e}")

        return None

    # HTMLタグを除去

    text = re.sub(r"<[^>]+>", " ", html)

    text = unescape(text)

    text = re.sub(r"\s+", " ", text)

    # 例：第1競走 16:25発走

    pattern = rf"第\s*{race_no}\s*競走.*?(\d{{1,2}}:\d{{2}})\s*発走"

    match = re.search(pattern, text)

    if not match:

        return None

    return match.group(1)

def get_fresh_schedule_file(folder, now):

    files = sorted(
        folder.glob("all_schedule_*.csv"),
        key=lambda p: p.name,
        reverse=True,
    )

    for file in files:
        match = re.fullmatch(r"all_schedule_(\\d{6})\\.csv", file.name)
        if not match:
            continue

        stamp = match.group(1)
        file_dt = datetime.strptime(
            f"{now.strftime('%Y-%m-%d')} {stamp}",
            "%Y-%m-%d %H%M%S",
        ).replace(tzinfo=JST)

        age_seconds = (now - file_dt).total_seconds()
        if 0 <= age_seconds < SCHEDULE_CACHE_MINUTES * 60:
            return file

    return None


def main():

    now = datetime.now(JST)

    race_date = now.date()

    folder = Path("data") / race_date.strftime("%Y-%m-%d")

    folder.mkdir(parents=True, exist_ok=True)

    fresh_schedule = get_fresh_schedule_file(folder, now)
    if fresh_schedule is not None:
        print(f"既存スケジュールを再利用: {fresh_schedule}")
        return

    rows = []

    print(f"開催確認開始: {race_date}")

    for track_name, track_code in TRACKS.items():

        track_rows = []

        print("")

        print(f"=== {track_name} ===")

        for race_no in range(1, 13):

            start_time = get_start_time(

                track_code,

                race_date,

                race_no

            )

            if start_time:

                print(f"{race_no}R {start_time}")

                row = {

                    "race_date": race_date.strftime("%Y-%m-%d"),

                    "track": track_name,

                    "track_code": track_code,

                    "race_no": race_no,

                    "start_time": start_time,

                }

                rows.append(row)

                track_rows.append(row)

            time.sleep(0.3)

        if not track_rows:

            print("本日の開催なし")

        else:

            print(f"{len(track_rows)}レース確認")
    # 日付限定の追加レース

    extra_key = race_date.strftime("%Y-%m-%d")

    for track_name, track_code, race_no in EXTRA_RACES.get(extra_key, []):

        start_time = get_start_time(

            track_code,

            race_date,

            race_no

        )

        if start_time:

            row = {

                "race_date": race_date.strftime("%Y-%m-%d"),

                "track": track_name,

                "track_code": track_code,

                "race_no": race_no,

                "start_time": start_time,

            }

            rows.append(row)

            print(f"追加: {track_name} {race_no}R {start_time}")

        time.sleep(0.3)
    rows.sort(

        key=lambda x: (

            x["start_time"],

            x["track"],

            x["race_no"]

        )

    )

    timestamp = now.strftime("%H%M%S")

    output_file = folder / f"all_schedule_{timestamp}.csv"

    with output_file.open(

        "w",

        newline="",

        encoding="utf-8-sig"

    ) as f:

        writer = csv.DictWriter(

            f,

            fieldnames=[

                "race_date",

                "track",

                "track_code",

                "race_no",

                "start_time",

            ]

        )

        writer.writeheader()

        writer.writerows(rows)

    print("")

    print("==============================")

    print(f"合計 {len(rows)}レース")

    print(f"保存先: {output_file}")

    print("==============================")

if __name__ == "__main__":

    main()

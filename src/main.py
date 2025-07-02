import argparse
import json
import numpy as np
import itertools
import re
import os
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta, timezone

import grits
from grits import grits_con, grits_top

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--predict", required=True, help="推論 (評価したい) データのパス")
    parser.add_argument("-g", "--grandtruth", required=True, help="正解データのパス")
    parser.add_argument("-s", "--score", required=True, help="スコアファイルの出力パス")
    args = parser.parse_args()

    # 抽出データのルートディレクトリパス
    pred_dir = Path(args.predict)
    # 正解データのルートディレクトリパス
    gt_dir = Path(args.grandtruth)
    # スコア記録用のルートディレクトリパス
    score_dir = Path(args.score)

    # スコア記録用のJSON
    # 日本時間のタイムゾーンを定義
    JST = timezone(timedelta(hours=+9), 'JST')
    # Pythonが動くサーバーのタイムゾーン設定に左右されずに日本時間の現在時刻を取得
    dt = datetime.now(JST)
    # ISO8601形式で表示,小数点以下の秒数が邪魔なので秒数までを表示する
    dt_now = dt.isoformat(timespec="seconds")
    scores_json = {"datetime": dt_now, "results": []}

    # Tableごとのスコアを表示するために、正解データのdoc_idとtable_idを控えておく
    temp_results = [[], []]
    # リコールの分母（正解の表の総数）
    recall_denom = len(list(gt_dir.glob("**/*")))
    # 各ツールごとに評価を行うため、まずは各ツールをForで回す
    pred_tools = pred_dir.glob("*")
    for pred_tool in pred_tools:
        # プレシジョンの分母（抽出した表の総数）
        precision_denom = len(list(pred_tool.glob("**/*")))
        temp_scores_json = {"tool": "", "num_tables": precision_denom, "scores": []}
        tool_name = pred_tool.name
        print(f"{tool_name=}")
        temp_scores_json["tool"] = re.sub(r"\d\d_", "", tool_name)
        # debug1
        if tool_name == "00_unstructured":
            continue
        # if tool_name != "00_AzureAiDocumentIntelligence":
            # continue
        # あるツールに対して、ドキュメントごとに処理
        for pred_doc in pred_tool.glob("*"):
        # for pred_doc in pred_tool.glob("*"):
            doc_id = pred_doc.name
            print(f"{doc_id=}")
            gt_doc = gt_dir.glob(f"*{doc_id}").__next__()
            print(f"{gt_doc.name=}")
            for gt_html in gt_doc.glob("*.html"):
                print(f"{gt_html.name=}")
                gt_html_name = gt_html.name
                # 正解と同名の抽出ファイルを取得
                pred_html = list(pred_doc.glob(f"{gt_html_name}"))
                # 同名のファイルが存在しない場合、スコアを0.0にする
                if len(pred_html) == 0:
                    metrics = {"grits_top": 0.0, "grits_con": 0.0}
                # 同名のファイルが一つだけ存在する場合、スコアを計算する
                elif len(pred_html) == 1:
                    pred_html = pred_html[0]
                    with open(pred_html, "r", encoding="utf-8") as f:
                        pred_html_text = convert_special_character_from_html(f.read())
                    with open(gt_html, "r", encoding="utf-8") as f:
                        gt_html_text = convert_special_character_from_html(f.read())
                    metrics = grits.grits_from_html(gt_html_text, pred_html_text)
                # 同名のファイルが2つ以上存在する場合、例外処理
                else:
                    raise ValueError(f"expect 1 but {len(pred_html)}")
                print(json.dumps(metrics, indent=2))
                score = {
                    "doc_id": doc_id,
                    "table_id": gt_html.stem,
                    "grits_top": metrics["grits_top"],
                    "grits_con": metrics["grits_con"]
                }
                temp_scores_json["scores"].append(score)
            # break
        scores_json["results"].append(temp_scores_json)
        # break

    # スコア情報のJSONを保存
    print(json.dumps(scores_json, indent=2))
    save_score_dir = score_dir / f"Score_{dt.strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(save_score_dir)
    with open((save_score_dir / "scores.json"), "w") as f:
        json.dump(scores_json, f, indent=2)

    # スコアの集計、可視化
    # 各ツールごとのTopとConのスコアを一覧にしたDataFrame（df_scores_each_tool）を作成
    df_scores_each_tool_columns=["tool", "top_recall", "top_precision", "top_F1", "con_recall", "con_precision", "con_F1"]
    scores_each_tool = []

    # 各スコアごとに（別DataFrameで）、Tableごとのスコアを一覧にしたDataFrame（df_scores_each_table）を作成
    doc_ids = []
    table_ids = []
    gt_docs = gt_dir.glob(f"*")
    for gt_doc in gt_docs:
        gt_doc_id = gt_doc.name
        for gt_html in gt_doc.glob("*.html"):
            gt_table_id = gt_html.stem
            doc_ids.append(gt_doc_id)
            table_ids.append(gt_table_id)
    df_scores_each_table_template = pd.DataFrame({"doc_id": doc_ids, "table_id": table_ids})
    df_scores_each_table_top = df_scores_each_table_template.copy()
    df_scores_each_table_con = df_scores_each_table_template.copy()

    for result in scores_json["results"]:
        scores_top_for_each_tool = []
        scores_con_for_each_tool = []
        tool_name = result["tool"]
        df_scores_each_table_top[tool_name] = 0.0
        df_scores_each_table_con[tool_name] = 0.0
        for score in result["scores"]:
            doc_id = score["doc_id"]
            table_id = score["table_id"]
            grits_top = score["grits_top"]
            grits_con = score["grits_con"]
            scores_top_for_each_tool.append(grits_top)
            scores_con_for_each_tool.append(grits_con)
            df_scores_each_table_top.loc[(df_scores_each_table_top["doc_id"] == doc_id) & (df_scores_each_table_top["table_id"] == table_id), tool_name] = grits_top
            df_scores_each_table_con.loc[(df_scores_each_table_con["doc_id"] == doc_id) & (df_scores_each_table_con["table_id"] == table_id), tool_name] = grits_con
        # 各スコアを計算
        sum_top = sum(scores_top_for_each_tool)
        sum_con = sum(scores_con_for_each_tool)
        recall_top = sum_top / recall_denom
        recall_con = sum_con / recall_denom
        precision_top = sum_top / precision_denom
        precision_con = sum_con / precision_denom
        f1_top = 2 * recall_top * precision_top / (recall_top + precision_top)
        f1_con = 2 * recall_con * precision_con / (recall_con + precision_con)
        scores = [recall_top, precision_top, f1_top, recall_con, precision_con, f1_con]
        scores_all = [f"{tool_name}"] + [round(i, 4) for i in scores]
        # scores_each_tool.append([tool_name, recall_top, precision_top, f1_top, recall_con, precision_con, f1_con])
        scores_each_tool.append(scores_all)

    df_scores_each_tool = pd.DataFrame(scores_each_tool, columns=df_scores_each_tool_columns)
    print(df_scores_each_tool)
    with open((save_score_dir / "scores_each_tool.csv"), "w", encoding="utf-8") as f:
        df_scores_each_tool.to_csv(f, index=False)
    print(df_scores_each_table_top)
    print(df_scores_each_table_con)
    with open((save_score_dir / "scores_each_table_top.csv"), "w", encoding="utf-8") as f:
        df_scores_each_table_top.to_csv(f, index=False)
    with open((save_score_dir / "scores_each_table_con.csv"), "w", encoding="utf-8") as f:
        df_scores_each_table_con.to_csv(f, index=False)

    # metrics = grits.grits_from_html(true_html, pred_html1)
    # print(json.dumps(metrics, indent=2))

# GriTSのパースの際、&の文字が含まれるとパースが失敗してしまうので、
# HTMLの特殊文字（&から始まる）を処理したあと、&の文字をHTMLの特殊文字（&amp;）に変換する
def convert_special_character_from_html(html_text: str):
    html_text = html_text.replace("&lt;", "<")
    html_text = html_text.replace("&gt;", ">")
    html_text = html_text.replace("&amp;", "&")
    html_text = html_text.replace("&quot;", "\"")
    html_text = html_text.replace("&#39;", "'")
    html_text = html_text.replace("&nbsp;", " ")
    html_text = html_text.replace("&", "&amp;")
    return html_text

if __name__ == "__main__":
    main()

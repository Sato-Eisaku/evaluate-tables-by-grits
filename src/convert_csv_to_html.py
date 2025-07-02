#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSVファイルをHTMLファイルに変換するスクリプト
ディレクトリ構造を保ったまま変換を行います
"""

import os
import csv
import argparse
from pathlib import Path
from typing import List, Optional
import html


def csv_to_html_table(csv_file_path: str, encoding: str = 'utf-8') -> str:
    """
    CSVファイルを読み込んでHTMLテーブルに変換する
    
    Args:
        csv_file_path: CSVファイルのパス
        encoding: ファイルエンコーディング
        
    Returns:
        HTMLテーブルの文字列
    """
    try:
        with open(csv_file_path, 'r', encoding=encoding, newline='') as csvfile:
            # CSVの区切り文字を自動検出
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.reader(csvfile, delimiter=delimiter)
            rows = list(reader)
            
        if not rows:
            return "空のCSVファイルです"
        
        # HTMLテーブルを生成
        html_content = ['<table>']
        
        # 全ての行をデータ行として扱う（ヘッダー/データの区別なし）
        for row in rows:
            html_content.append('<tr>')
            for cell in row:
                escaped_cell = html.escape(str(cell))
                html_content.append(f'<td>{escaped_cell}</td>')
            html_content.append('</tr>')
        
        html_content.append('</table>')
        return '\n'.join(html_content)
        
    except UnicodeDecodeError:
        # UTF-8で読めない場合はShift_JISを試す
        try:
            return csv_to_html_table(csv_file_path, encoding='shift_jis')
        except:
            return f"エラー: ファイル '{csv_file_path}' を読み込めませんでした（エンコーディングエラー）"
    except Exception as e:
        return f"エラー: {html.escape(str(e))}"

def convert_csv_files(input_dir: str, output_dir: str, extensions: List[str] = None) -> None:
    """
    指定されたディレクトリ内のCSVファイルをHTMLに変換する
    
    Args:
        input_dir: 入力ディレクトリ
        output_dir: 出力ディレクトリ
        extensions: 対象ファイル拡張子のリスト
    """
    if extensions is None:
        extensions = ['.csv']
    
    input_path = Path(input_dir)
    output_path = Path(output_dir) / input_path.stem
    
    if not input_path.exists():
        print(f"エラー: 入力ディレクトリ '{input_dir}' が存在しません")
        return
    
    # 出力ディレクトリを作成
    output_path.mkdir(parents=True, exist_ok=True)
    
    converted_count = 0
    error_count = 0
    
    # ディレクトリを再帰的に走査
    for file_path in input_path.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            # 相対パスを取得
            relative_path = file_path.relative_to(input_path)
            
            # 出力ファイルパス（拡張子を.htmlに変更）
            output_file_path = output_path / relative_path.with_suffix('.html')
            
            # 出力ディレクトリを作成
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"変換中: {relative_path}")
            
            try:
                # CSVをHTMLテーブルに変換
                table_html = csv_to_html_table(str(file_path))

                # HTMLファイルを書き出し
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(table_html)
                
                converted_count += 1
                print(f"  → {output_file_path}")
                
            except Exception as e:
                error_count += 1
                print(f"  エラー: {e}")
    
    print(f"\n変換完了: {converted_count}ファイル変換済み, {error_count}エラー")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="CSVファイルをHTMLファイルに変換します（ディレクトリ構造を保持）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python csv_to_html.py input_folder output_folder
  python csv_to_html.py /path/to/csv/files /path/to/html/output
  python csv_to_html.py data html_output --extensions .csv .tsv
        """
    )
    
    parser.add_argument(
        'input_dir',
        help='CSVファイルが格納されている入力ディレクトリ'
    )
    
    parser.add_argument(
        'output_dir',
        help='HTMLファイルを出力するディレクトリ'
    )
    
    parser.add_argument(
        '--extensions',
        nargs='+',
        default=['.csv'],
        help='変換対象のファイル拡張子（デフォルト: .csv）'
    )
    
    args = parser.parse_args()
    
    print(f"入力ディレクトリ: {args.input_dir}")
    print(f"出力ディレクトリ: {args.output_dir}")
    print(f"対象拡張子: {args.extensions}")
    print("-" * 50)
    
    convert_csv_files(args.input_dir, args.output_dir, args.extensions)


if __name__ == "__main__":
    main()
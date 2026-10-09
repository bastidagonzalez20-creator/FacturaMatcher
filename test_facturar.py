import unittest
import tempfile
import os
import csv
from datetime import date, time, datetime
import pandas as pd
import numpy as np

# Adjust imports based on the actual facturar_app module
from facturar_app import (
    parse_date, parse_time, normalize_am_pm, fmt_es, build_date,
    parse_any_datetime, format_es_ampm, normalize_spanish_ampm,
    normalize_tel_series, parse_datetime_spanish, find_column,
    sniff_delimiter, try_open_reader, _iso_ms_re, finalize_coincidencias
)

class TestDateParsing(unittest.TestCase):
    def test_parse_date_ddmmyyyy(self):
        self.assertEqual(parse_date('01/12/2025'), date(2025, 12, 1))

    def test_parse_date_ddmmyyyy_dash(self):
        self.assertEqual(parse_date('01-12-2025'), date(2025, 12, 1))

    def test_parse_date_iso(self):
        self.assertEqual(parse_date('2025-12-01'), date(2025, 12, 1))

    def test_parse_date_short_year(self):
        self.assertEqual(parse_date('01/12/25'), date(2025, 12, 1))

    def test_parse_date_empty(self):
        self.assertIsNone(parse_date(''))

    def test_parse_date_none(self):
        self.assertIsNone(parse_date(None))

    def test_parse_date_invalid(self):
        self.assertIsNone(parse_date('not a date'))


class TestTimeParsing(unittest.TestCase):
    def test_parse_time_24h(self):
        self.assertEqual(parse_time('14:30:00'), time(14, 30, 0))

    def test_parse_time_24h_no_sec(self):
        self.assertEqual(parse_time('14:30'), time(14, 30, 0))

    def test_parse_time_12h_am(self):
        self.assertEqual(parse_time('02:30:00 AM'), time(2, 30, 0))

    def test_parse_time_12h_pm(self):
        self.assertEqual(parse_time('02:30:00 PM'), time(14, 30, 0))

    def test_parse_time_spanish_am(self):
        self.assertEqual(parse_time('02:30:00 a. m.'), time(2, 30, 0))

    def test_parse_time_spanish_pm(self):
        self.assertEqual(parse_time('02:30:00 p. m.'), time(14, 30, 0))

    def test_parse_time_empty(self):
        self.assertIsNone(parse_time(''))

    def test_parse_time_none(self):
        self.assertIsNone(parse_time(None))


class TestDateFormatting(unittest.TestCase):
    def test_fmt_es_am(self):
        dt = datetime(2025, 12, 1, 8, 30, 0)
        self.assertEqual(fmt_es(dt), '01/12/2025 08:30:00 a. m.')

    def test_fmt_es_pm(self):
        dt = datetime(2025, 12, 1, 14, 30, 0)
        self.assertEqual(fmt_es(dt), '01/12/2025 02:30:00 p. m.')

    def test_fmt_es_midnight(self):
        dt = datetime(2025, 12, 1, 0, 0, 0)
        self.assertEqual(fmt_es(dt), '01/12/2025 12:00:00 a. m.')

    def test_fmt_es_noon(self):
        dt = datetime(2025, 12, 1, 12, 0, 0)
        self.assertEqual(fmt_es(dt), '01/12/2025 12:00:00 p. m.')


class TestParseAnyDatetime(unittest.TestCase):
    def test_parse_any_iso(self):
        dt = parse_any_datetime('2025-12-01 08:56:08.487')
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 12)
        self.assertEqual(dt.day, 1)
        self.assertEqual(dt.hour, 8)
        self.assertEqual(dt.minute, 56)
        self.assertEqual(dt.second, 8)
        self.assertEqual(dt.microsecond, 487000)

    def test_parse_any_iso_no_ms(self):
        self.assertEqual(parse_any_datetime('2025-12-01 08:56:08'), datetime(2025, 12, 1, 8, 56, 8))

    def test_parse_any_ddmmyyyy_24h(self):
        self.assertEqual(parse_any_datetime('01/12/2025 14:30:00'), datetime(2025, 12, 1, 14, 30, 0))

    def test_parse_any_ddmmyyyy_12h_spanish(self):
        self.assertEqual(parse_any_datetime('01/12/2025 02:30:00 a. m.'), datetime(2025, 12, 1, 2, 30, 0))

    def test_parse_any_empty(self):
        self.assertIsNone(parse_any_datetime(''))

    def test_parse_any_none(self):
        self.assertIsNone(parse_any_datetime(None))


class TestFormatEsAmpm(unittest.TestCase):
    def test_format_es_ampm(self):
        dt = datetime(2025, 12, 1, 14, 30, 0)
        self.assertEqual(format_es_ampm(dt), '01/12/2025 02:30:00 p. m.')


class TestTelephoneNormalization(unittest.TestCase):
    def test_tel_digits_only(self):
        series = pd.Series(['55-1234-5678'])
        res = normalize_tel_series(series)
        self.assertEqual(res.iloc[0], '5512345678')

    def test_tel_with_country_52(self):
        series = pd.Series(['525512345678'])
        res = normalize_tel_series(series)
        self.assertEqual(res.iloc[0], '5512345678')

    def test_tel_with_country_521(self):
        series = pd.Series(['5215512345678'])
        res = normalize_tel_series(series)
        self.assertEqual(res.iloc[0], '5512345678')

    def test_tel_short(self):
        series = pd.Series(['12345'])
        res = normalize_tel_series(series)
        self.assertTrue(pd.isna(res.iloc[0]))

    def test_tel_long(self):
        series = pd.Series(['005215512345678'])
        res = normalize_tel_series(series)
        self.assertEqual(res.iloc[0], '5512345678')


class TestColumnDetection(unittest.TestCase):
    def setUp(self):
        self.columns = ['ID', 'Fecha de Conexión', 'Nombre', 'Teléfono']

    def test_find_column_exact(self):
        self.assertEqual(find_column(self.columns, ['Fecha de Conexión']), 'Fecha de Conexión')

    def test_find_column_no_accent(self):
        self.assertEqual(find_column(self.columns, ['Fecha de Conexion']), 'Fecha de Conexión')

    def test_find_column_case_insensitive(self):
        self.assertEqual(find_column(self.columns, ['fecha de conexión']), 'Fecha de Conexión')

    def test_find_column_missing(self):
        self.assertIsNone(find_column(self.columns, ['Nonexistent']))

    def test_find_column_broken_utf8(self):
        cols = ['Fecha de ConexiÃ³n']
        self.assertEqual(find_column(cols, ['Fecha de Conexión']), 'Fecha de ConexiÃ³n')


class TestBuildDate(unittest.TestCase):
    def test_build_date_normal(self):
        d = date(2025, 12, 1)
        t = time(14, 30, 0)
        self.assertEqual(build_date(d, t), '01/12/2025 02:30:00 p. m.')

    def test_build_date_no_time(self):
        d = date(2025, 12, 1)
        self.assertEqual(build_date(d, None), '01/12/2025 12:00:00 a. m.')

    def test_build_date_no_date(self):
        t = time(14, 30, 0)
        self.assertEqual(build_date(None, t), '01/01/1900 02:30:00 p. m.')

    def test_build_date_both_none(self):
        self.assertEqual(build_date(None, None), '')


class TestCSVReadingIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sniff_delimiter_comma(self):
        filepath = os.path.join(self.temp_dir.name, 'comma.csv')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("A,B,C\n1,2,3")
        
        delim = sniff_delimiter(filepath)
        self.assertEqual(delim, ',')

    def test_sniff_delimiter_semicolon(self):
        filepath = os.path.join(self.temp_dir.name, 'semi.csv')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("A;B;C\n1;2;3")
        
        delim = sniff_delimiter(filepath)
        self.assertEqual(delim, ';')

    def test_sniff_delimiter_tab(self):
        filepath = os.path.join(self.temp_dir.name, 'tab.csv')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("A\tB\tC\n1\t2\t3")
        
        delim = sniff_delimiter(filepath)
        self.assertEqual(delim, '\t')

    def test_try_open_reader(self):
        filepath = os.path.join(self.temp_dir.name, 'data.csv')
        with open(filepath, 'w', encoding='latin1') as f:
            f.write("Nombre,Edad\nJosé,30")
            
        reader, fh, enc = try_open_reader(filepath)
        try:
            rows = list(reader)
            # csv.reader returns lists; first row is header, second is data
            self.assertEqual(len(rows), 2)
            self.assertIn("Jos", rows[1][0])
        finally:
            fh.close()


class TestFinalizeCoincidencias(unittest.TestCase):
    def test_finalize_coincidencias_drops_columns_and_adds_cw_minutes(self):
        data = {
            'id': [1, 2],
            'date': ['2025-10-01', '2025-10-02'],
            'telephone': ['5512345678', '5587654321'],
            'CW_dialog': [120, 300],
            'CW_agent': ['AgentA', 'AgentB'],
            'TIER_CRUCE': ['exact_minute', '±1min'],
            'DELTA_SEGUNDOS': [0.0, 45.0]
        }
        df = pd.DataFrame(data)
        res = finalize_coincidencias(df)
        
        # Verify columns dropped
        for col in ['TIER_CRUCE', 'DELTA_SEGUNDOS', 'date', 'telephone']:
            self.assertNotIn(col, res.columns)
            
        # Verify CW_minutes exists and position is directly after CW_dialog
        cols = list(res.columns)
        self.assertIn('CW_minutes', cols)
        cw_dialog_idx = cols.index('CW_dialog')
        cw_minutes_idx = cols.index('CW_minutes')
        self.assertEqual(cw_minutes_idx, cw_dialog_idx + 1)
        
        # Verify values: 120/60 = 2.0, 300/60 = 5.0
        self.assertAlmostEqual(res['CW_minutes'].iloc[0], 2.0)
        self.assertAlmostEqual(res['CW_minutes'].iloc[1], 5.0)

    def test_finalize_coincidencias_no_cw_dialog(self):
        data = {
            'id': [1],
            'date': ['2025-10-01'],
            'telephone': ['5512345678'],
            'TIER_CRUCE': ['exact_minute'],
            'DELTA_SEGUNDOS': [0.0]
        }
        df = pd.DataFrame(data)
        res = finalize_coincidencias(df)
        for col in ['TIER_CRUCE', 'DELTA_SEGUNDOS', 'date', 'telephone']:
            self.assertNotIn(col, res.columns)
        self.assertNotIn('CW_minutes', res.columns)


if __name__ == '__main__':
    unittest.main()


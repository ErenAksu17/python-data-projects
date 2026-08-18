// Shape of the processed dataset produced by the Python pipeline
// (data/processed/renewable.json). Kept in sync with analyze.py.

export interface Trend {
  years: number[];
  values: number[];
}

export interface Forecast {
  method: string;
  r2: number;
  slope_pct_per_year: number;
  holdout_years: number[];
  model_rmse: number | null;
  model_mae: number | null;
  model_mape: number | null;
  naive_rmse: number | null;
  beats_naive: boolean | null;
  forecast_years: number[];
  forecast_values: number[];
  forecast_low: number[];
  forecast_high: number[];
}

export interface Sector {
  code: string;
  label: string;
  value: number;
  year: number;
}

export interface Country {
  geo: string;
  name: string;
  iso2: string;
  latest_year: number;
  latest_value: number;
  ref_value: number | null;
  cagr: number | null;
  trend: Trend;
  rank?: number;
}

export interface RankRow {
  rank: number;
  geo: string;
  name: string;
  iso2: string;
  value: number;
}

export interface ResEOver100 {
  geo: string;
  name: string;
  iso2: string;
  value: number;
  year: number;
}

export interface Dataset {
  meta: {
    source: string;
    source_url: string;
    license: string;
    generated_at: string;
    reference_year: number;
  };
  target: { pct: number; year: number };
  eu: {
    geo: string;
    name: string;
    latest: { year: number; value: number; provisional: boolean };
    gap_to_target: number;
    trend: Trend;
    sectors: Sector[];
    forecast: Forecast;
  };
  countries: Country[];
  ranking: RankRow[];
  insights: { res_e_over_100: ResEOver100[]; reference_year: number };
}

from pydantic import BaseModel, ConfigDict


class CalibrationBinResponse(BaseModel):
    bin_lower: float
    bin_upper: float
    count: int
    mean_predicted: float
    mean_actual: float


class CalibrationMetricResponse(BaseModel):
    brier_score: float
    log_loss: float
    accuracy: float
    calibration_error: float
    auc_roc: float = 0.0
    n_matches: int = 0


class BiasReportResponse(BaseModel):
    home_bias: float
    favorite_bias: float
    draw_bias: float
    underdog_bias: float
    high_confidence_bias: float
    low_confidence_bias: float


class ConfederationBiasResponse(BaseModel):
    confederation: str
    match_count: int
    brier_score: float
    accuracy: float
    home_win_pred: float
    home_win_actual: float
    favorite_pred: float
    favorite_actual: float
    draw_pred: float
    draw_actual: float


class FavoriteBiasResponse(BaseModel):
    bracket_lower: float
    bracket_upper: float
    count: int
    mean_predicted_prob: float
    mean_actual_win_rate: float


class DrawBiasResponse(BaseModel):
    match_count: int
    predicted_draw_rate: float
    actual_draw_rate: float
    bias: float


class HomeBiasResponse(BaseModel):
    match_count: int
    predicted_home_win_rate: float
    actual_home_win_rate: float
    bias: float


class OutcomeCalibrationCurveResponse(BaseModel):
    outcome: str
    bins: list[CalibrationBinResponse] = []


class ModelComparisonMetricResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_name: str
    overall: CalibrationMetricResponse
    by_tournament: dict[str, CalibrationMetricResponse] = {}
    by_stage: dict[str, CalibrationMetricResponse] = {}


class BenchmarkReportResponse(BaseModel):
    models: list[ModelComparisonMetricResponse] = []
    best_model: str = ""
    improvement_vs_baseline: dict[str, float] = {}


class CalibrationReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    overall: CalibrationMetricResponse
    by_tournament: dict[str, CalibrationMetricResponse] = {}
    by_stage: dict[str, CalibrationMetricResponse] = {}
    calibration_curve: list[CalibrationBinResponse] = []
    outcome_curves: list[OutcomeCalibrationCurveResponse] = []
    bias: BiasReportResponse | None = None
    confederation_biases: list[ConfederationBiasResponse] = []
    favorite_biases: list[FavoriteBiasResponse] = []
    draw_bias_detail: DrawBiasResponse | None = None
    home_bias_detail: HomeBiasResponse | None = None
    match_count: int = 0
    weight_adjustments: dict[str, float] = {}
    benchmark: BenchmarkReportResponse | None = None

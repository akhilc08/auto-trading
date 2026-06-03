"""exec-trend-following Flight entrypoint.

Runs the nine trend_following-account strategies (EXEC-03) on MotherDuck compute, reading Alpaca
credentials from the `alpaca_trend_following` secret. Reuses the plan 02-02 scaffold.
"""
from flights.exec._runner import run_account_flight


def main():
    run_account_flight(
        account_name="trend_following",
        strategy_names=[
            "trend_following",
            "trend_following_v2",
            "multi_factor_equity",
            "multi_factor_equity_v2",
            "regime_switching",
            "post_earnings_drift",
            "rl_alpha",
            "deep_learning",
            "alt_data_fusion",
        ],
        secret_name="alpaca_trend_following",
    )


if __name__ == "__main__":
    main()

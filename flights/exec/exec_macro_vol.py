"""exec-macro-vol Flight entrypoint.

Runs the macro_vol-account strategy (vol_risk_premium) on MotherDuck compute, reading Alpaca
credentials from the `alpaca_macro_vol` secret. Reuses the plan 02-02 scaffold.
"""
from flights.exec._runner import run_account_flight


def main():
    run_account_flight(
        account_name="macro_vol",
        strategy_names=["vol_risk_premium"],
        secret_name="alpaca_macro_vol",
    )


if __name__ == "__main__":
    main()

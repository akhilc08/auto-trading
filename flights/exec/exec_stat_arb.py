"""exec-stat-arb Flight entrypoint.

Runs the five stat_arb-account strategies on MotherDuck compute, reading Alpaca credentials
from the `alpaca_stat_arb` MotherDuck secret. Deployed as a MotherDuck Flight whose
requirements install this repo (see flights/exec/requirements.txt + the git+ repo line).
"""
from flights.exec._runner import run_account_flight


def main():
    run_account_flight(
        account_name="stat_arb",
        strategy_names=[
            "stat_arb",
            "stat_arb_v2",
            "stat_arb_v3",
            "market_neutral",
            "market_neutral_v2",
        ],
        secret_name="alpaca_stat_arb",
    )


if __name__ == "__main__":
    main()

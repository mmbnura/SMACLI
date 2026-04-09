from src.bootstrap import bootstrap_master_data


if __name__ == "__main__":
    count = bootstrap_master_data()
    print(f"Database initialized. stocks_master rows: {count}")

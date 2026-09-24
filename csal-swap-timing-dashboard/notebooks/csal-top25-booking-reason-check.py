# Databricks Python cell. Run after CSAL_TIMELINE_COVERAGE_CHECK.
# Read-only: uses the saved selected bookings and reads current booking reasons.
from uuid import uuid4
import re
import pandas as pd
from pyspark.sql import types as T


def run_csal_booking_reason_check():
    timeline = globals().get("CSAL_TIMELINE_COVERAGE_CHECK")
    if not isinstance(timeline, dict) or timeline.get("status") != "COMPLETED":
        raise ValueError("Run the timeline coverage cell successfully first.")

    matched = timeline.get("matched")
    needed = {"shipment_num", "f_bkg_status", "l_bkg_status",
              "bkg_cre_iodt", "f_pd_iodt", "f_rej_iodt"}
    if not isinstance(matched, pd.DataFrame) or not needed.issubset(matched.columns):
        raise ValueError("The saved timeline is missing required columns.")
    if matched.empty or matched.shipment_num.isna().any() or matched.shipment_num.duplicated().any():
        raise ValueError("Selected shipment numbers are empty, missing or repeated.")
    if "join_result" in matched and not matched.join_result.eq("Exactly one timeline row").all():
        raise ValueError("The saved timeline includes unresolved shipment matches.")

    def label(value):
        return "(missing)" if pd.isna(value) or not str(value).strip() else " ".join(str(value).split())

    def has_time(value):
        return int(not pd.isna(value) and bool(re.fullmatch(
            r"\d{14}(\.\d{1,9})?", str(value).strip())))

    records = [
        (str(row.shipment_num).strip().upper(), label(row.f_bkg_status),
         label(row.l_bkg_status), has_time(row.bkg_cre_iodt),
         has_time(row.f_pd_iodt), has_time(row.f_rej_iodt))
        for row in matched.itertuples(index=False)
    ]
    if len({row[0] for row in records}) != len(records):
        raise ValueError("Normalized shipment numbers are repeated.")

    source = "datasources.csal.csal_booking_detail"
    available = set(spark.table(source).columns)
    if "shipment_num" not in available:
        raise ValueError("Booking detail has no shipment_num column.")
    reason_sql = ("NULLIF(TRIM(CAST(d.status_internal_reason AS STRING)), '')"
                  if "status_internal_reason" in available else "CAST(NULL AS STRING)")
    status_sql = ("NULLIF(TRIM(CAST(d.shipment_status AS STRING)), '')"
                  if "shipment_status" in available else "CAST(NULL AS STRING)")

    schema = T.StructType([
        T.StructField("shipment_num", T.StringType(), False),
        T.StructField("first_status", T.StringType(), False),
        T.StructField("last_status", T.StringType(), False),
        T.StructField("has_creation_date", T.IntegerType(), False),
        T.StructField("has_first_pending_date", T.IntegerType(), False),
        T.StructField("has_first_rejected_date", T.IntegerType(), False),
    ])
    view = "csal_reason_keys_" + uuid4().hex[:10]
    spark.createDataFrame(records, schema).createOrReplaceTempView(view)
    try:
        query = f"""
        WITH detail AS (
          SELECT UPPER(TRIM(CAST(d.shipment_num AS STRING))) shipment_num,
                 COUNT(*) detail_rows,
                 COUNT(DISTINCT COALESCE({reason_sql}, '<NULL>')) reason_versions,
                 MIN({reason_sql}) current_reason,
                 COUNT(DISTINCT COALESCE({status_sql}, '<NULL>')) status_versions,
                 MIN({status_sql}) current_status
          FROM {source} d
          LEFT SEMI JOIN {view} k
            ON UPPER(TRIM(CAST(d.shipment_num AS STRING))) = k.shipment_num
          GROUP BY UPPER(TRIM(CAST(d.shipment_num AS STRING)))
        ), joined AS (
          SELECT k.*,
                 CASE WHEN d.shipment_num IS NULL THEN 'NO_DETAIL_ROW'
                      WHEN d.reason_versions > 1 OR d.status_versions > 1 THEN 'CONFLICTING_CURRENT_VALUES'
                      ELSE 'ONE_CURRENT_VALUE' END current_value_check,
                 CASE WHEN d.reason_versions = 1 THEN d.current_reason END current_reason,
                 CASE WHEN d.status_versions = 1 THEN d.current_status END current_status
          FROM {view} k LEFT JOIN detail d ON k.shipment_num = d.shipment_num
        )
        SELECT first_status, last_status, current_value_check,
               COALESCE(current_status, '(missing)') current_status,
               COALESCE(current_reason, '(blank or unresolved)') current_reason,
               COUNT(*) bookings,
               SUM(has_creation_date) with_creation_date,
               SUM(has_first_pending_date) with_first_pending_date,
               SUM(has_first_rejected_date) with_first_rejected_date
        FROM joined
        GROUP BY first_status, last_status, current_value_check,
                 COALESCE(current_status, '(missing)'),
                 COALESCE(current_reason, '(blank or unresolved)')
        """
        table = spark.sql(query).limit(5001).toPandas()
        if len(table) > 5000:
            raise ValueError("More than 5,000 reason/status groups; the compact report was not produced.")
        if int(table.bookings.sum()) != len(records):
            raise ValueError("Reason/status groups do not reconcile to the selected bookings.")

        summary = (table.groupby(["first_status", "last_status", "current_value_check"],
                                 as_index=False)[["bookings", "with_creation_date",
                                                  "with_first_pending_date",
                                                  "with_first_rejected_date"]].sum()
                   .sort_values("bookings", ascending=False))
        top = table.sort_values("bookings", ascending=False).head(40)
        print("BEGIN CSAL BOOKING REASON CHECK")
        print(f"Selected bookings: {len(records):,} | Reason source: {source}")
        print("1. Timeline first/last status and date coverage")
        print(summary.to_csv(sep="\t", index=False).rstrip())
        print("2. Forty most common current reason/status combinations")
        print(top.to_csv(sep="\t", index=False).rstrip())
        print(f"Other combinations: {len(table)-len(top):,}; bookings in other combinations: "
              f"{int(table.bookings.sum()-top.bookings.sum()):,}")
        print("Current reason is not necessarily the reason when a booking first pended or was rejected.")
        print("A first Pended date alone does not mean the customer asked for extra space.")
        print("No customer request or added TEU total is inferred here.")
        print("END CSAL BOOKING REASON CHECK")
        return {"status": "COMPLETED", "summary": summary, "reason_groups": table}
    finally:
        spark.catalog.dropTempView(view)


CSAL_BOOKING_REASON_CHECK = run_csal_booking_reason_check()

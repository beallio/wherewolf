import streamlit as st
from wherewolf.constants import DIALECT_MAPPING
from wherewolf.execution import QueryResult
from wherewolf.export import Exporter
from wherewolf.translation import Translator


def encode_export(df, export_format: str):
    """Encodes a DataFrame to (bytes, mime, extension) for the given format."""
    if export_format == "CSV":
        return Exporter.to_csv(df), "text/csv", ".csv"
    if export_format == "Excel":
        return (
            Exporter.to_excel(df),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        )
    return Exporter.to_parquet(df), "application/octet-stream", ".parquet"


def export_base_name() -> str:
    """Derives a base filename for exports from the first catalog entry."""
    import os

    if st.session_state.catalog:
        first_path = list(st.session_state.catalog.values())[0]
        orig_filename = os.path.basename(first_path)
        return os.path.splitext(orig_filename)[0] or "wherewolf"
    return "wherewolf"


class ResultsView:
    @staticmethod
    def render(result: QueryResult, translator: Translator, get_engine) -> None:
        """Render translation, metrics, preview, and export UI for a query result."""
        if result.success:
            # --- Translation Section ---
            st.divider()
            col_t1, col_t2 = st.columns([0.7, 0.3])
            with col_t1:
                st.subheader("SQL Translation")
            with col_t2:
                # Map the EXECUTED input dialect to key for consistent translation logic
                executed_input_key = st.session_state.executed_input_dialect_key

                # Determine target options: everything except the EXECUTED input dialect
                target_options = [
                    ui_name for ui_name, key in DIALECT_MAPPING.items() if key != executed_input_key
                ]

                selected_target_ui = st.selectbox(
                    "Target Dialect", options=target_options, label_visibility="collapsed"
                )

                # Map UI selection to SQLGlot dialect identifiers
                target_dialect = DIALECT_MAPPING[selected_target_ui]

            try:
                # Translate from the EXECUTED query and dialect
                translated_sql = translator.translate(
                    st.session_state.executed_query,
                    from_dialect=executed_input_key,
                    to_dialect=target_dialect,
                )
                with st.expander(f"Translated SQL ({selected_target_ui})", expanded=True):
                    st.code(translated_sql, language="sql")
            except Exception as e:
                st.warning(f"Translation failed: {str(e)}")

            m1, m2 = st.columns(2)
            if result.is_truncated:
                m1.metric("Rows Previewed", f"{result.row_count:,}")
                st.caption(f"Note: Preview is truncated at {result.row_count} rows.")
            else:
                m1.metric("Rows Returned", f"{result.row_count:,}")
            m2.metric("Execution Time", f"{result.execution_time:.4f}s")

            st.subheader("Preview")
            st.dataframe(result.df, width="stretch")

            # --- Export Section ---
            st.divider()
            st.subheader("Export Results")

            col_e1, col_e2 = st.columns([0.2, 0.8])
            with col_e1:
                export_format = st.selectbox(
                    "Export Format",
                    ["CSV", "Excel", "Parquet"],
                    label_visibility="collapsed",
                )

            base_name = export_base_name()

            with col_e2:
                data, mime, ext = encode_export(result.df, export_format)
                if result.is_truncated:
                    export_label = (
                        f"Download preview ({result.row_count:,} rows) as {export_format}"
                    )
                else:
                    export_label = f"Download as {export_format}"
                download_name = f"{base_name}_export{ext}"
                st.download_button(
                    label=export_label, data=data, file_name=download_name, mime=mime
                )

            # When the preview is truncated, offer a full-result export. This re-runs
            # the executed query without a row limit, so it is opt-in via a button.
            if result.is_truncated:
                st.caption(
                    "The preview above is truncated. Generate a full export to download the "
                    "entire result set (this re-runs the query without a row limit)."
                )
                if st.button("Prepare full export"):
                    full_engine = get_engine(st.session_state.executed_engine_name)

                    with st.spinner("Running full query..."):
                        full_result = full_engine.execute(
                            st.session_state.executed_engine_query,
                            "",
                            None,
                            st.session_state.catalog.copy(),
                        )

                    if full_result.success:
                        f_data, f_mime, f_ext = encode_export(full_result.df, export_format)
                        st.session_state.full_export = {
                            "data": f_data,
                            "mime": f_mime,
                            "file_name": f"{base_name}_full{f_ext}",
                            "rows": full_result.row_count,
                            "format": export_format,
                        }
                    else:
                        st.session_state.full_export = None
                        st.error(f"Full export failed: {full_result.error_message}")

                full_export = st.session_state.full_export
                if full_export and full_export["format"] == export_format:
                    st.download_button(
                        label=f"Download full result ({full_export['rows']:,} rows) as {export_format}",
                        data=full_export["data"],
                        file_name=full_export["file_name"],
                        mime=full_export["mime"],
                        key="full_export_download",
                    )
                elif full_export:
                    st.caption(
                        f"A full export is ready in {full_export['format']} format. "
                        "Switch the format selector back or press 'Prepare full export' again."
                    )

        else:
            st.error("Query Failed")
            with st.expander("Show Details"):
                st.text(result.error_message)

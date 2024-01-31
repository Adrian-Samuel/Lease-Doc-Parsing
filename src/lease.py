import re
from typing import List, Optional, Tuple

from loguru import logger
from pdfplumber.pdf import PDF
from pydantic import BaseModel


class LeaseDocument(BaseModel):
    number: Optional[int] = None
    title: Optional[str] = None
    registration_date_with_plan_ref: Optional[str] = None
    property_description: Optional[str] = None
    date_with_term: Optional[str] = None
    notes: Optional[List[str]] = []


class ColumnMapping(BaseModel):
    word_position: int
    words: list[str]


class LeaseParser:
    # definition should just be the first string of an array
    def _define_column_mappings(
        self, column_defining_row: str, cached_positions: Optional[List[int]]
    ) -> Tuple[ColumnMapping, List[int]]:
        column_mapping: ColumnMapping = {}

        first_column_date, third_column_date = re.findall(
            "\d{2}\.\d{2}\.\d{4}", column_defining_row
        )
        first_column_position = column_defining_row.find(first_column_date)
        third_column_position = column_defining_row.find(third_column_date)

        # we know the title id is defined by a specific pattern
        (lease_title,) = re.findall("([A-Z]+\d+)", column_defining_row)
        lease_id_position = column_defining_row.find(lease_title)

        first_column_end_position = first_column_position + len(first_column_date)
        second_column_end_position = third_column_position - 1

        # since the second column is the only one in the first row without a unique identifying pattern,
        # a cached position has value here

        second_column = column_defining_row[
            first_column_end_position:second_column_end_position
        ].strip()
        if len(cached_positions) > 0:
            second_column_positon = cached_positions[1]
        else:
            second_column_positon = column_defining_row.find(second_column)

        column_mapping = {
            1: {"position": first_column_position, "words": [first_column_date]},
            2: {"position": second_column_positon, "words": [second_column]},
            3: {"position": third_column_position, "words": [third_column_date]},
            4: {
                "position": lease_id_position,
                "words": [lease_title],
            },
        }
        column_positions = [value["position"] for _, value in column_mapping.items()]
        return column_mapping, column_positions

    def _map_rows_to_columns(
        self, column_mapping: ColumnMapping, remaining_rows: list[str]
    ) -> ColumnMapping:
        for row_num, row in enumerate(remaining_rows):
            # current row is +2 because lists are zero indexed and we've already gone through the first index
            current_row = row_num + 2
            logger.info(f"The current row is {current_row}")

            column_one = row[
                column_mapping[1]["position"] : column_mapping[2]["position"]
            ].strip()
            column_two = row[
                column_mapping[2]["position"] : column_mapping[3]["position"]
            ].strip()
            column_three = row[
                column_mapping[3]["position"] : column_mapping[4]["position"]
            ].strip()

            column_mapping[1]["words"].append(column_one)
            column_mapping[2]["words"].append(column_two)
            column_mapping[3]["words"].append(column_three)
        return column_mapping

    def _extract_lease_records(self, pdf: PDF):
        start_table_pattern = "and plan ref."
        end_table_pattern = "\n\d+ of \d+"
        table_beginning_header = "Schedule of notices of leases"
        unmarshalled_lease_records = []
        for page in pdf.pages:
            # retrieve raw text with the whitespace retained
            text = page.extract_text_simple()
            # check to see it's a page containing lease records
            if table_beginning_header in text and page.page_number:
                logger.info(f"The page is {page.page_number}")
                _, page_table_and_footer = text.split(start_table_pattern)
                page_table, _ = re.split(end_table_pattern, page_table_and_footer)
                lease_record = re.split("\\n\d+\s+(\d{2}\.\d{2}\.\d{4})", page_table)
                if lease_record != "":
                    unmarshalled_lease_records.extend(lease_record)

        partial_lease_record = []
        merged_lease_records = []
        for item in unmarshalled_lease_records:
            # on partial result (partial results always begin with new line delimeters)
            if re.match("^\\n.*", item):
                # modify previous entry to include split field
                last_inserted_merged_lease_record = len(merged_lease_records) - 1
                merged_lease_records[last_inserted_merged_lease_record] += item
                continue

                # if record contains the beginning date
            if re.match("\d{2}\.\d{2}\.\d{4}", item):
                partial_lease_record.append(item)
                continue
            else:
                # if previous result contained partial record, merge them
                if len(partial_lease_record) == 1:
                    fixed_record = partial_lease_record[0] + item
                    partial_lease_record = []
                    merged_lease_records.append(fixed_record)

        # fix last record values where "End of Register" is added
        last_lease_record_index = len(merged_lease_records) - 1
        merged_lease_records[last_lease_record_index] = merged_lease_records[
            len(merged_lease_records) - 1
        ].split("\nEnd of register")[0]

        return merged_lease_records

    def _parse_records(self, extracted_lease_records):
        processed_records = []
        column_positions_reconciler = {
            "reconciled": False,
            "positions": [],
            "merger_list": [],
        }
        for idx, lease_record in enumerate(extracted_lease_records):
            # records start with one, not zero
            lease_record_number = idx + 1

            logger.info(f"Lease record no: {idx + 1}")

            lease_record_without_notes = None
            matched_notes = re.findall("NOTE:.*\n?.*", lease_record)
            notes = []
            if matched_notes:
                for note in matched_notes:
                    notes.append(note)
                lease_record_without_notes = re.split("NOTE:.*\n?.*", lease_record)[0]
            else:
                lease_record_without_notes = lease_record

            record_rows = re.split("\n", lease_record_without_notes)
            first_column = record_rows[0]
            remaining_columns = record_rows[1:]

            column_mapping, column_positions = self._define_column_mappings(
                first_column, column_positions_reconciler["positions"]
            )

            # cache mismatched positions until a correct one is found (handles edge case on record 411)
            if not column_positions_reconciler["reconciled"]:
                for existing_position_list in column_positions_reconciler[
                    "merger_list"
                ]:
                    # compare positions to see if there are common positions
                    if existing_position_list == column_positions:
                        column_positions_reconciler["reconciled"] = True
                        column_positions_reconciler["positions"] = column_positions
                        break
                    # if no two matching positions found then add it to the comparison list
                if not column_positions_reconciler["reconciled"]:
                    column_positions_reconciler["merger_list"].append(column_positions)

            column_data = self._map_rows_to_columns(column_mapping, remaining_columns)

            formatted_lease_records = []
            for row in column_data.values():
                # apply spacing between joined strings then strip whitespace
                formatted_row = " ".join(row["words"]).strip()
                formatted_lease_records.append(formatted_row)
            (
                reg_with_plan_ref,
                property_description,
                date_with_term,
                title,
            ) = formatted_lease_records

            lease_data = LeaseDocument(
                number=lease_record_number,
                title=title,
                registration_date_with_plan_ref=reg_with_plan_ref,
                property_description=property_description,
                date_with_term=date_with_term,
                notes=notes,
            )
            processed_records.append(lease_data)
        return processed_records

    def marshal_lease_data(self, lease_document: PDF):
        merged_lease_records = self._extract_lease_records(lease_document)
        return self._parse_records(merged_lease_records)

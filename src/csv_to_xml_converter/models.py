# src/csv_to_xml_converter/models.py
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import json # Added for testing to_xml_dict outputs

@dataclass
class IntermediateRecord:
    """Base class for records processed by the rule engine."""
    raw_input_data: Optional[Dict[str, Any]] = field(default=None, repr=False)
    errors: List[str] = field(default_factory=list)

@dataclass
class II_Element: # Helper for Instance Identifier (II)
    root: Optional[str] = None
    extension: Optional[str] = None

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        if self.root is not None: data["root"] = self.root
        if self.extension is not None: data["extension"] = self.extension
        return data

@dataclass
class CD_Element: # Helper for Coded Value (CD)
    code: Optional[str] = None
    code_system: Optional[str] = None
    code_system_name: Optional[str] = None # Optional: some systems use OID for codeSystem
    display_name: Optional[str] = None

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        if self.code is not None: data["code"] = self.code
        if self.code_system is not None: data["code_system"] = self.code_system
        if self.code_system_name is not None: data["code_system_name"] = self.code_system_name
        if self.display_name is not None: data["display_name"] = self.display_name
        return data

@dataclass
class MO_Element_Data: # Helper for Monetary (MO) elements with currency
    value: Optional[str] = None
    currency: str = "JPY"

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        if self.value is not None: data["value"] = self.value
        if self.currency is not None: data["currency"] = self.currency
        return data

@dataclass
class CDAHeaderData(IntermediateRecord): # Inherits from IntermediateRecord
    # Document Level
    document_id: Optional[II_Element] = None
    type_id: Optional[II_Element] = None # e.g. POCD_HD000040
    document_type: Optional[CD_Element] = None # e.g. Specific Health Checkup Information
    document_title: Optional[str] = None
    document_effective_time: Optional[str] = None # YYYYMMDD or YYYYMMDDHHMMSS
    confidentiality: Optional[CD_Element] = None
    language_code: str = "ja-JP"

    # Patient
    patient_id_mrn: Optional[II_Element] = None
    patient_id_insurance_no: Optional[II_Element] = None
    patient_name_family: Optional[str] = None
    patient_name_given: Optional[str] = None
    patient_gender: Optional[CD_Element] = None
    patient_birth_time_value: Optional[str] = None # YYYYMMDD

    # Author
    author_id: Optional[II_Element] = None
    # Assuming author is an institution for now. If person, more fields needed.

    # Custodian
    custodian_id: Optional[II_Element] = None # Represented Custodian Organization ID

    # Service Event (documentationOf/serviceEvent)
    service_event_effective_time_low: Optional[str] = None # YYYYMMDD
    service_event_effective_time_high: Optional[str] = None # YYYYMMDD
    # service_event_id: Optional[II_Element] = None # If needed for serviceEvent/id

    # errors field is inherited from IntermediateRecord

    def __post_init__(self):
        # Initialize nested dataclasses if None to allow direct attribute access
        if hasattr(super(), '__post_init__'): # Ensure parent __post_init__ is called if it exists
            super().__post_init__()
        if self.document_id is None: self.document_id = II_Element()
        if self.type_id is None: self.type_id = II_Element()
        if self.document_type is None: self.document_type = CD_Element()
        if self.confidentiality is None: self.confidentiality = CD_Element()
        if self.patient_id_mrn is None: self.patient_id_mrn = II_Element()
        if self.patient_id_insurance_no is None: self.patient_id_insurance_no = II_Element()
        if self.patient_gender is None: self.patient_gender = CD_Element()
        if self.author_id is None: self.author_id = II_Element()
        if self.custodian_id is None: self.custodian_id = II_Element()

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        # Document Level
        if self.document_id and (self.document_id.root is not None or self.document_id.extension is not None):
            if self.document_id.root is not None: data["documentIdRootOid"] = self.document_id.root
            if self.document_id.extension is not None: data["documentIdExtension"] = self.document_id.extension
        if self.type_id and (self.type_id.root is not None or self.type_id.extension is not None):
            if self.type_id.root is not None: data["typeIdRootOid"] = self.type_id.root
            if self.type_id.extension is not None: data["typeIdExtension"] = self.type_id.extension
        if self.document_type and (self.document_type.code is not None or self.document_type.display_name is not None):
            if self.document_type.code is not None: data["documentTypeCode"] = self.document_type.code
            if self.document_type.code_system is not None: data["documentTypeCodeSystem"] = self.document_type.code_system
            if self.document_type.display_name is not None: data["documentTypeDisplayName"] = self.document_type.display_name
        if self.document_title is not None: data["documentTitle"] = self.document_title
        if self.document_effective_time is not None: data["documentEffectiveTime"] = self.document_effective_time
        if self.confidentiality and (self.confidentiality.code is not None or self.confidentiality.display_name is not None) :
            if self.confidentiality.code is not None: data["confidentialityCode"] = self.confidentiality.code
            if self.confidentiality.code_system is not None: data["confidentialityCodeSystem"] = self.confidentiality.code_system
            if self.confidentiality.display_name is not None: data["confidentialityDisplayName"] = self.confidentiality.display_name
        if self.language_code is not None: data["languageCode"] = self.language_code

        # Patient
        if self.patient_id_mrn and (self.patient_id_mrn.root is not None or self.patient_id_mrn.extension is not None):
            if self.patient_id_mrn.root is not None: data["patientIdMrnRootOid"] = self.patient_id_mrn.root
            if self.patient_id_mrn.extension is not None: data["patientIdMrnExtension"] = self.patient_id_mrn.extension
        if self.patient_id_insurance_no and (self.patient_id_insurance_no.root is not None or self.patient_id_insurance_no.extension is not None):
            if self.patient_id_insurance_no.root is not None: data["patientIdInsuranceNoRootOid"] = self.patient_id_insurance_no.root
            if self.patient_id_insurance_no.extension is not None: data["patientIdInsuranceNoExtension"] = self.patient_id_insurance_no.extension
        if self.patient_name_family is not None: data["patientNameFamily"] = self.patient_name_family
        if self.patient_name_given is not None: data["patientNameGiven"] = self.patient_name_given
        if self.patient_gender and (self.patient_gender.code is not None or self.patient_gender.display_name is not None):
            if self.patient_gender.code is not None: data["patientGenderCode"] = self.patient_gender.code
            if self.patient_gender.code_system is not None: data["patientGenderCodeSystem"] = self.patient_gender.code_system
            if self.patient_gender.display_name is not None: data["patientGenderDisplayName"] = self.patient_gender.display_name
        if self.patient_birth_time_value is not None: data["patientBirthTimeValue"] = self.patient_birth_time_value

        # Author
        if self.author_id and (self.author_id.root is not None or self.author_id.extension is not None):
            if self.author_id.root is not None: data["authorIdRootOid"] = self.author_id.root
            if self.author_id.extension is not None: data["authorIdExtension"] = self.author_id.extension

        # Custodian
        if self.custodian_id and (self.custodian_id.root is not None or self.custodian_id.extension is not None):
            if self.custodian_id.root is not None: data["custodianIdRootOid"] = self.custodian_id.root
            if self.custodian_id.extension is not None: data["custodianIdExtension"] = self.custodian_id.extension

        # Service Event
        if self.service_event_effective_time_low is not None: data["serviceEventEffectiveTimeLow"] = self.service_event_effective_time_low
        if self.service_event_effective_time_high is not None: data["serviceEventEffectiveTimeHigh"] = self.service_event_effective_time_high

        return {k: v for k, v in data.items() if v is not None} # Remove None values

@dataclass
class ObservationDataItem:
    # Code for the observation item itself
    item_code: Optional[CD_Element] = None

    # Value of the observation
    value: Optional[Any] = None # Could be str, int, float
    value_type: Optional[str] = None # PQ, CD, INT, ST, etc. to guide XML generation
    unit: Optional[str] = None # For PQ values

    # If value is a coded concept (value_type='CD')
    value_code_system: Optional[str] = None
    value_code_system_name: Optional[str] = None
    value_display_name: Optional[str] = None

    # Interpretation, reference range, etc. can be added later
    # errors field can be inherited if ObservationDataItem itself becomes an IntermediateRecord,
    # or handled by the parent model that holds it. For now, let's keep it simple.
    # errors: List[str] = field(default_factory=list) # Keeping it local for now

    def __post_init__(self):
        # if hasattr(super(), '__post_init__'): super().__post_init__()
        if self.item_code is None: self.item_code = CD_Element()

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        # This is a simplified version. For complex cases like observations needing prefixed keys
        # (e.g., "item_heightCode", "item_height_value"), the XML generator will need to be adapted
        # to work with the model structure directly or this method needs to be much more complex
        # and potentially take a prefix argument.
        if self.item_code and (self.item_code.code is not None or self.item_code.display_name is not None):
            # Flatten CD_Element fields into the current dict without prefix,
            # assuming the caller or a more specific model's to_xml_dict handles naming.
            # For example, if this ObservationDataItem is `self.height`, then HealthCheckupRecord.to_xml_dict()
            # would need to prefix these as `heightCode`, `heightCodeSystem` etc.
            # This is still not ideal for direct use with existing XML generators.
            # For now, this returns item_code.* fields directly.
            data.update(self.item_code.to_xml_dict()) # Merges keys like 'code', 'code_system'

        if self.value is not None: data["value"] = str(self.value) # Ensure value is string
        if self.value_type is not None: data["value_type"] = self.value_type
        if self.unit is not None: data["unit"] = self.unit

        # These are for when value itself is a code (value_type='CD')
        # The XML generator for observations usually handles value/@code, value/@codeSystem etc.
        # This simple to_xml_dict might not map perfectly to that structure without more context.
        if self.value_code_system is not None: data["value_code_system"] = self.value_code_system
        if self.value_code_system_name is not None: data["value_code_system_name"] = self.value_code_system_name
        if self.value_display_name is not None: data["value_display_name"] = self.value_display_name

        return {k: v for k, v in data.items() if v is not None}

@dataclass
class ObservationGroup:
    # Code for the panel or group itself
    panel_code: Optional[CD_Element] = None
    # classCode for the parent observation (e.g., "CLUSTER" for panels)
    panel_class_code: str = "CLUSTER"
    components: List[ObservationDataItem] = field(default_factory=list)
    # errors: List[str] = field(default_factory=list) # Keeping it local for now

    def __post_init__(self):
        # if hasattr(super(), '__post_init__'): super().__post_init__()
        if self.panel_code is None: self.panel_code = CD_Element()

@dataclass
class HealthCheckupRecord(IntermediateRecord): # Inherits from IntermediateRecord
    header: CDAHeaderData = field(default_factory=CDAHeaderData)

    # Specific fields for hc08 body
    height: Optional[ObservationDataItem] = None
    weight: Optional[ObservationDataItem] = None
    bmi: Optional[ObservationDataItem] = None
    waist_circumference: Optional[ObservationDataItem] = None
    systolic_bp: Optional[ObservationDataItem] = None
    diastolic_bp: Optional[ObservationDataItem] = None

    lab_test_results: List[ObservationDataItem] = field(default_factory=list)
    lab_test_panels: List[ObservationGroup] = field(default_factory=list)

    results_section_code: Optional[CD_Element] = None
    results_section_title: Optional[str] = "検査結果"

    # raw_input_data and errors are inherited from IntermediateRecord

    def __post_init__(self):
        if hasattr(super(), '__post_init__'): super().__post_init__()
        if self.results_section_code is None: self.results_section_code = CD_Element()
        if self.header is None: self.header = CDAHeaderData() # Ensure header is initialized

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        if self.header: # Ensure header is not None
            data.update(self.header.to_xml_dict())

        # Add simple, flat body attributes that xml_generator might expect in the main dict
        if self.results_section_code and (self.results_section_code.code is not None or self.results_section_code.display_name is not None):
            # XML generator expects: section_ResultsCode, section_ResultsCodeSystem, section_ResultsDisplayName
            if self.results_section_code.code is not None: data["section_ResultsCode"] = self.results_section_code.code
            if self.results_section_code.code_system is not None: data["section_ResultsCodeSystem"] = self.results_section_code.code_system
            if self.results_section_code.display_name is not None: data["section_ResultsDisplayName"] = self.results_section_code.display_name
        if self.results_section_title is not None: data["section_ResultsTitle"] = self.results_section_title

        # For complex body elements like lists of observations (self.height, self.weight, self.lab_test_results),
        # the xml_generator will be modified later to access them directly from the model instance.
        # This to_xml_dict() will not try to flatten them for now as it's too complex
        # and error-prone without knowing the exact prefixes the generator expects for each item.
        return {k: v for k, v in data.items() if v is not None}

@dataclass
class HealthGuidanceRecord(IntermediateRecord): # Inherits from IntermediateRecord
    header: CDAHeaderData = field(default_factory=CDAHeaderData)

    guidance_program_name: Optional[str] = None
    guidance_classification: Optional[ObservationDataItem] = None

    initial_interview_section_code: Optional[CD_Element] = None
    initial_interview_section_title: Optional[str] = "初回面接情報"
    initial_interview_points: Optional[ObservationDataItem] = None

    guidance_observations: List[ObservationDataItem] = field(default_factory=list)
    guidance_groups: List[ObservationGroup] = field(default_factory=list)

    # raw_input_data and errors are inherited from IntermediateRecord

    def __post_init__(self):
        if hasattr(super(), '__post_init__'): super().__post_init__()
        if self.initial_interview_section_code is None: self.initial_interview_section_code = CD_Element()
        if self.header is None: self.header = CDAHeaderData() # Ensure header is initialized

    def to_xml_dict(self) -> Dict[str, Any]:
        data = {}
        if self.header: # Ensure header is not None
            data.update(self.header.to_xml_dict())

        # Add simple, flat body attributes
        if self.guidance_program_name is not None: data["guidanceProgramName"] = self.guidance_program_name # Check generator key

        if self.initial_interview_section_code and \
           (self.initial_interview_section_code.code is not None or self.initial_interview_section_code.display_name is not None):
            # Prefixes like "section_InitialInterview"
            if self.initial_interview_section_code.code is not None: data["section_InitialInterviewCode"] = self.initial_interview_section_code.code
            if self.initial_interview_section_code.code_system is not None: data["section_InitialInterviewCodeSystem"] = self.initial_interview_section_code.code_system
            if self.initial_interview_section_code.display_name is not None: data["section_InitialInterviewDisplayName"] = self.initial_interview_section_code.display_name
        if self.initial_interview_section_title is not None: data["section_InitialInterviewTitle"] = self.initial_interview_section_title

        # Complex body elements (guidance_classification, initial_interview_points, lists)
        # will be handled by direct model access in the generator later.
        return {k: v for k, v in data.items() if v is not None}

@dataclass
class CheckupSettlementRecord(IntermediateRecord): # Inherits from IntermediateRecord
    document_id_ext: Optional[str] = None
    encounter_details: Optional[str] = "Checkup Encounter"

    patient_id_mrn: Optional[II_Element] = None
    checkup_org_id: Optional[II_Element] = None
    insurer_id: Optional[II_Element] = None

    copayment_type: Optional[CD_Element] = None

    claim_type: Optional[CD_Element] = None
    commission_type: Optional[CD_Element] = None

    total_points_value: Optional[str] = None
    total_cost_value: Optional[str] = None
    copayment_amount_value: Optional[str] = None
    claim_amount_value: Optional[str] = None

    # raw_input_data and errors are inherited from IntermediateRecord

    def __post_init__(self):
        if hasattr(super(), '__post_init__'): super().__post_init__()
        if self.patient_id_mrn is None: self.patient_id_mrn = II_Element()
        if self.checkup_org_id is None: self.checkup_org_id = II_Element()
        if self.insurer_id is None: self.insurer_id = II_Element()
        if self.copayment_type is None: self.copayment_type = CD_Element()
        if self.claim_type is None: self.claim_type = CD_Element()
        if self.commission_type is None: self.commission_type = CD_Element()

    def to_xml_dict(self) -> Dict[str, Any]:
        # Assumes rule engine populates attributes directly with names expected by XML generator.
        # Exclude helper dataclass fields and standard IntermediateRecord fields.
        excluded_fields = {'raw_input_data', 'errors',
                           'patient_id_mrn', 'checkup_org_id', 'insurer_id',
                           'copayment_type', 'claim_type', 'commission_type'}
        data = {k: v for k, v in vars(self).items() if v is not None and k not in excluded_fields}

        # Manually handle nested II_Elements if they were populated by rules (which they aren't currently for settlement)
        # For now, this simple vars(self) relies on rules directly setting patientIdMrnRootOid etc.
        return data

@dataclass
class GuidanceSettlementRecord(IntermediateRecord): # Inherits from IntermediateRecord
    document_id: Optional[II_Element] = None

    author_institution_id: Optional[II_Element] = None

    patient_id_mrn: Optional[II_Element] = None
    insurer_id: Optional[II_Element] = None

    encounter_guidance_org_id: Optional[II_Element] = None
    guidance_level: Optional[CD_Element] = None
    timing: Optional[CD_Element] = None

    copayment_type_hg_card: Optional[CD_Element] = None
    points_completed_value: Optional[str] = None
    points_intended_value: Optional[str] = None

    total_cost_settlement: Optional[MO_Element_Data] = None
    copayment_amount_settlement: Optional[MO_Element_Data] = None
    claim_amount_settlement: Optional[MO_Element_Data] = None

    # raw_input_data and errors are inherited from IntermediateRecord

    def __post_init__(self):
        if hasattr(super(), '__post_init__'): super().__post_init__()
        if self.document_id is None: self.document_id = II_Element()
        if self.author_institution_id is None: self.author_institution_id = II_Element()
        if self.patient_id_mrn is None: self.patient_id_mrn = II_Element()
        if self.insurer_id is None: self.insurer_id = II_Element()
        if self.encounter_guidance_org_id is None: self.encounter_guidance_org_id = II_Element()
        if self.guidance_level is None: self.guidance_level = CD_Element()
        if self.timing is None: self.timing = CD_Element()
        if self.copayment_type_hg_card is None: self.copayment_type_hg_card = CD_Element()
        if self.total_cost_settlement is None: self.total_cost_settlement = MO_Element_Data()
        if self.copayment_amount_settlement is None: self.copayment_amount_settlement = MO_Element_Data() # Ensure default initialization
        if self.claim_amount_settlement is None: self.claim_amount_settlement = MO_Element_Data() # Ensure default initialization


    def to_xml_dict(self) -> Dict[str, Any]:
        # Assumes rule engine populates attributes directly with names expected by XML generator.
        excluded_fields = {'raw_input_data', 'errors',
                           'document_id', 'author_institution_id', 'patient_id_mrn',
                           'insurer_id', 'encounter_guidance_org_id',
                           'guidance_level', 'timing', 'copayment_type_hg_card',
                           'total_cost_settlement', 'copayment_amount_settlement', 'claim_amount_settlement'}
        data = {k: v for k, v in vars(self).items() if v is not None and k not in excluded_fields}

        # Manually handle nested elements if they were populated by rules
        # For now, this simple vars(self) relies on rules directly setting documentIdRootOid etc.
        return data

# Self-test / example usage

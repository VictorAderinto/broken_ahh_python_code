# Handle skipping questions
def skipped_questions(field, answers):
    field_value = answers.get(field, '').lower()

    if field == 'other_names' and field_value == 'no':
        return 2
    if field == 'resided_other_countries' and field_value == 'no':
        return 9
    if field == 'resided_other_countries_2' and field_value == 'no':
        return 4
    if field == 'country_applying_from_same' and field_value == 'no':
        return 4
    if field == 'marital_status' and field_value not in ['married', 'common-law']:
        return 15
    if field == 'partner_email' and answers.get('marital_status', '').lower() == 'married':
        return 7
    if field == 'previous_relationship' and field_value == 'no':
        return 6
    if field == 'uci_issued' and field_value == 'no':
        return 1
    if field == 'nin_document' and field_value == 'no':
        return 4
    if field == 'us_permanent_resident' and field_value == 'no':
        return 2
    if field == 'mailing_address_same' and field_value == 'yes':
        return 1
    if field == 'has_alternate_phone' and field_value == 'no':
        return 5
    if field == 'has_fax_number' and field_value == 'no':
        return 4
    if field == 'has_provincial_attestation' and field_value == 'no':
        return 2
    if field == 'has_caq' and field_value == 'no':
        return 2
    if field == 'has_post_secondary_education' and field_value == 'no':
        return 8
    if field == 'employment_other' and field_value == 'no':
        return 17
    if field == 'employment_other_2' and field_value == 'no':
        return 8
    if field == 'physical_or_mental_disorder' and field_value == 'no' and answers.get('tuberculosis_exposure',
                                                                                      '').lower() == 'no':
        return 1
    if field == 'previous_application_canada' and field_value == 'no' and answers.get('visa_or_entry_refused',
                                                                                      '').lower() == 'no' and answers.get(
            'status_violation_canada', '').lower() == 'no':
        return 1
    if field == 'criminal_history' and field_value == 'no':
        return 1
    if field == 'military_or_security_service' and field_value == 'no':
        return 5
    if field == 'has_children' and field_value == 'no':
        return 27
    if field == 'has_children_2' and field_value == 'no':
        return 17
    if field == 'has_children_3' and field_value == 'no':
        return 8
    if field == 'has_siblings' and field_value == 'no':
        return 9
    if field == 'has_siblings_2' and field_value == 'no':
        return 9
    if field == 'has_siblings_3' and field_value == 'no':
        return 9
    if field == 'minor_status' and field_value == 'no':
        return 6
    if field == 'uci_issued' and field_value == 'no':
        return 1

    # No skip needed for 'check_eligibility' here, as that breaks the loop

    # if q26 answer = yes then q26=q11, q27=q12, q28=q13, q29=q14
    if field == 'country_applying_from_same' and field_value == 'yes':
        # autofill answers for related fields
        answers['country_applying_from'] = answers.get('residence_country', '')
        answers['status_country_applying_from'] = answers.get('residence_status', '')
        answers['current_country_start_date'] = answers.get('residence_status_start_date', '')
        answers['current_country_end_date'] = answers.get('residence_status_end_date', '')
        return 4
    if field == 'mailing_address_same' and field_value == 'yes':
        answers['residential_address'] = answers.get('mailing_address', '')
        return 1
    return 0


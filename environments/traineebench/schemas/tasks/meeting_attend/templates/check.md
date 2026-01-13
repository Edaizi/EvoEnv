Below is the content discussed in the meeting. Please summarize the meeting content according to the output format and save it to `Workspace://meeting_summary.json`. When summarizing the meeting, please first review `CloudDisk://financial/procurement_rules.md` to ensure that all procurement requests are reasonable. Only record reasonable procurement requests in the output file; requests that do not conform to the rules do not need to be recorded.

# Meeting Topic: Procurement Requirement Statistics Meeting

## Meeting Details

{% if users and users|length > 0 %}
Procurement needs of each attendees:
{% for user in users %}
  - {{ user.person_name }}: {{ user.requirements }}
{% endfor %}
{% endif %}

# Output Format

Please summarize the meeting in the following format:

```json
{ 
    "requirement": [
        {
            "name": <person_name>,
            "item": <item_name>,
            "quantity": <item_quantity>,
            "unit_price": <unit_price>,
            "total" <total_amount_each_person>
        },
        {
            "name": <person_name>,
            "item": <item_name>,
            "quantity": <item_quantity>,
            "unit_price": <unit_price>,
            "total" <total_amount_each_person>
        },
    ]
}
```
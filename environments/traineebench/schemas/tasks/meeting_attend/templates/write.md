Below is the content discussed in the meeting. Please summarize the meeting content according to the output format and save it to `Workspace://meeting_summary.json`.

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
            "unit_price": <Unit Price>
        },
        {
            "name": <person_name>,
            "item": <item_name>,
            "quantity": <item_quantity>,
            "unit_price": <Unit Price>
        },
    ]
}
```
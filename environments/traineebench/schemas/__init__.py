from environments.traineebench.schemas.tasks.attendance.evaluation import *
from environments.traineebench.schemas.tasks.event_planning.evaluation import *
from environments.traineebench.schemas.tasks.transactions.evaluation import evaluate_abnormal_supplier
from environments.traineebench.schemas.tasks.meeting_book.evaluation import evaluation_meeting_booking_manager
from environments.traineebench.schemas.tasks.sales.evaluation import *
from environments.traineebench.schemas.tasks.kb_fix.evaluation import *
from environments.traineebench.schemas.tasks.data_completion.evaluation import *
from environments.traineebench.schemas.tasks.meeting_attend.evaluation import (
    evaluation_attending_meeting_none,
    evaluation_attending_meeting_sum,
    evaluation_attending_meeting_write,
    evaluation_attending_meeting_check_sum,
    evaluation_attending_meeting_check
)
from environments.traineebench.schemas.tasks.resume_select.evaluation import evaluate_resume_selection
from environments.traineebench.schemas.tasks.website_analysis.evaluation import evaluate_website_analysis
from environments.traineebench.schemas.tasks.ads_strategy.evaluation import evaluate_ads_optimal_strategy

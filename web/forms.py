from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SubmitField,
    BooleanField,
    IntegerField,
    SelectField,
)
from wtforms.validators import DataRequired, Optional
from flask_wtf.file import FileField

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Post Comment')

class ProjectForm(FlaskForm):
    title = StringField('Project Title', validators=[DataRequired()])
    description = TextAreaField('Project Description', validators=[DataRequired()])
    is_public = BooleanField('Make this project public')
    location = StringField('Sampling Location', validators=[Optional()])
    depth_min = IntegerField('Minimum Depth (m)', validators=[Optional()])
    depth_max = IntegerField('Maximum Depth (m)', validators=[Optional()])
    tags = StringField('Tags', validators=[Optional()])
    collaborators = StringField('Collaborators', validators=[Optional()])
    submit = SubmitField('Create Project')


class SampleUploadForm(FlaskForm):
    # Core sample info
    name = StringField('Sample Name', validators=[DataRequired()])
    description = TextAreaField('Sample Description', validators=[Optional()])
    collection_date = StringField('Collection Date', validators=[Optional()])
    location = StringField('Collection Location', validators=[Optional()])
    depth = IntegerField('Collection Depth (m)', validators=[Optional()])
    sample_type = SelectField(
        'Sample Type',
        choices=[
            ('water', 'Water'),
            ('sediment', 'Sediment'),
            ('biofilm', 'Biofilm'),
            ('organism', 'Organism'),
            ('other', 'Other'),
        ],
        validators=[Optional()],
    )

    # Files
    file = FileField('Sequence File')
    metadata_file = FileField('Metadata File (Optional)')

    # Analysis options
    run_analysis = BooleanField('Run analysis immediately after upload')
    analysis_type = SelectField(
        'Analysis Type',
        choices=[('standard', 'Standard'), ('novel', 'Novel Discovery'), ('fast', 'Fast Mode')],
        validators=[Optional()],
    )
    quality_filtering = BooleanField('Quality filtering')
    adapter_trimming = BooleanField('Adapter trimming')
    length_filtering = BooleanField('Length filtering')
    classification_model = SelectField(
        'Classification Model',
        choices=[('cnn', 'CNN'), ('transformer', 'Transformer'), ('hybrid', 'Hybrid')],
        validators=[Optional()],
    )
    confidence_threshold = IntegerField('Confidence Threshold', validators=[Optional()])
    
    submit = SubmitField('Upload Sample')

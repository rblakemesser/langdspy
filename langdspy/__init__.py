from langchain.prompts import BasePromptTemplate  # Assuming this is the correct import path
from langchain.prompts import FewShotPromptTemplate
from langchain_core.runnables import RunnableSerializable
from langchain_core.pydantic_v1 import BaseModel, Field, create_model, root_validator, Extra
from langchain_core.pydantic_v1 import validator
from langchain_core.language_models import BaseLLM

from typing import Any, Dict, List, Type, Optional
from abc import ABC, abstractmethod
from langchain_core.runnables.utils import (
    Input,
    Output
)
from langchain_core.runnables.config import (
    RunnableConfig
)

class FieldDescriptor:
    def __init__(self, name:str, desc: str):
        self.name = name
        self.desc = desc

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value):
        setattr(obj, self.private_name, value)

class InputField(FieldDescriptor):
    pass

class OutputField(FieldDescriptor):
    pass

class Prediction(BaseModel):
    class Config:
        extra = Extra.allow  # This allows the model to accept extra fields that are not explicitly declared

    def __init__(self, **kwargs):
        super().__init__(**kwargs)  # Initialize BaseModel with kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)  # Dynamically assign attributes

class PromptSignature(BasePromptTemplate, BaseModel):
    # Assuming input_variables and output_variables are defined as class attributes
    input_variables: Dict[str, Any] = []
    output_variables: Dict[str, Any] = []

    def __init__(self, **kwargs):
        # print(dir(self.__class__))
        # print("Calling super")
        # Temporarily bypassing the setting of input and output variables
        super().__init__(**kwargs)
        # print("Done super")
        # print(self.__class__.__fields__)

        inputs = {}
        outputs = {}

        for name, attribute in self.__class__.__fields__.items():
            # print(f"field: {name}, value: {attribute}")

            if attribute.type_ == InputField:
                inputs[name] = attribute.default
            elif attribute.type_ == OutputField:
                outputs[name] = attribute.default

        self.input_variables = inputs
        self.output_variables = outputs

        # print(f"Inputs: {self.input_variables}")
        # print(f"Outputs: {self.output_variables}")

class PromptStrategy(BaseModel):
    pass


class DefaultPromptStrategy(PromptStrategy):
    def format_prompt(self, **kwargs: Any) -> str:
        self.validate_inputs(kwargs)

        print("Formatting prompt")
        print(f"Input variables: self.input_variables: {self.input_variables}")

        prompt = "Follow the following format.\n\n"
        for input_name, input_field in self.input_variables.items():
            prompt += f"{input_field.name}: {input_field.desc}\n"

        prompt += "\n---\n\n"

        for input_name, input_field in self.input_variables.items():
            prompt += f"{input_field.name}: {kwargs.get(input_name)}\n"
        return prompt

    def validate_inputs(self, inputs_dict):
        assert set(inputs_dict.keys()) == set(self.input_variables.keys()), "Input keys do not match expected input keys"

    def format(self, **kwargs: Any) -> str:
        return self.format_prompt(**kwargs)
        
class PromptRunner(RunnableSerializable):
    template: PromptSignature = None

    def __init__(self, template_class, prompt_strategy):
        print(f"Initializing prompt runner")
        super().__init__()
        cls_ = type(template_class.__name__, (prompt_strategy, template_class), {})
        self.template = cls_()
    
    @validator("template")
    def check_template(
        cls, value: PromptSignature
    ) -> PromptSignature:
        print(f"Checking template: {value}")
        return value
    
    def invoke(self, input: Input, config: Optional[RunnableConfig] = None) -> Output:
        # print(f"Prompt runner {self.template.__class__.__name__} invoked with input: {input}")
        # prompt = self.template.format(**input)
        # print(f"Prompt: {prompt}")

        chain = (
            self.template
            | config['llm']
        )

        res = chain.invoke(input)
        print(res)

        # res = config['llm'].invoke(prompt, config)
        # print(f"Prompt runner {self.template.__class__.__name__} invoked with input: {input} and prompt: {prompt} and got response: {res}")

        return res

    def __call__(self, **kwargs):
        return self.invoke(kwargs)

class Model(RunnableSerializable):
    prompt_runners = []

    def __init__(self):
        super().__init__()

        for field_name, field in self.__fields__.items():
            if issubclass(field.type_, PromptRunner):
                self.prompt_runners.append((field_name, field.default))